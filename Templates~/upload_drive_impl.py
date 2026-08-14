#!/usr/bin/env python3
"""PEARZ / UMP Google Drive uploader using OAuth 2.0 user credentials.

Required environment variables:
    UMP_DRIVE_OAUTH_CLIENT_ID
    UMP_DRIVE_OAUTH_CLIENT_SECRET
    UMP_DRIVE_OAUTH_REFRESH_TOKEN
    UMP_DRIVE_FOLDER_ID

Destination behavior:
    Android: <root>/<Game name>/<APK|AAB>/<artifact>
    iOS info-only mode: <root>/<Game name>/IOS/<GameName>_BUILD_INFO.txt

- Missing folders are created automatically.
- Same-name file in the same folder is UPDATED, not recreated. This keeps
  the same Drive file id / shared link and creates a new revision.
- Older same-name duplicates are trashed unless UMP_DRIVE_KEEP_DUPLICATES=1.
- UMP_DRIVE_SUBPATH overrides the generated subpath; an explicitly empty
  value uploads directly into UMP_DRIVE_FOLDER_ID.
- If <GameName>_BUILD_INFO.txt exists beside the artifact (or directly under
  Builds/), it is uploaded into the SAME Drive folder as the artifact. Its
  Drive name gets a version suffix, e.g. MeowTrail_BUILD_INFO_v1.2.3.txt.
  Rebuilding the same version updates that same Drive file/revision.
- UMP_DRIVE_BUILD_INFO_ONLY=1 uploads exactly the supplied *_BUILD_INFO.txt
  into <Game name>/IOS, without a version suffix, without a companion upload,
  and without replacing Builds/ump_drive_url.txt.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URI = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
CHUNK_SIZE = 8 * 1024 * 1024  # Drive resumable chunks: multiple of 256 KiB.


def log(message):
    print("[PEARZ] " + str(message), flush=True)


def opener():
    # Drive replies 308 Resume Incomplete between resumable upload chunks.
    # urllib otherwise treats 308 as a redirect; keep it visible to the caller.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    return urllib.request.build_opener(NoRedirect)


def http(request):
    return opener().open(request, timeout=120)


def read_http_error(error):
    try:
        return error.read().decode(errors="replace")
    except Exception:
        return ""


def oauth_access_token():
    client_id = os.environ.get("UMP_DRIVE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("UMP_DRIVE_OAUTH_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("UMP_DRIVE_OAUTH_REFRESH_TOKEN", "").strip()

    missing = [
        name
        for name, value in (
            ("UMP_DRIVE_OAUTH_CLIENT_ID", client_id),
            ("UMP_DRIVE_OAUTH_CLIENT_SECRET", client_secret),
            ("UMP_DRIVE_OAUTH_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing OAuth credential(s): " + ", ".join(missing))

    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()

    request = urllib.request.Request(
        TOKEN_URI,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    log("Auth: OAuth 2.0 refresh token")

    try:
        with http(request) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = read_http_error(error)
        raise RuntimeError(
            "OAuth token refresh failed (HTTP %s): %s" % (error.code, detail)
        ) from error

    access_token = payload.get("access_token", "")
    if not access_token:
        raise RuntimeError("Google OAuth response did not contain access_token.")

    return access_token


def auth_headers(access_token, extra=None):
    headers = {"Authorization": "Bearer " + access_token}
    if extra:
        headers.update(extra)
    return headers


def folder_id_from_value(value):
    value = (value or "").strip()
    if "/folders/" in value:
        value = value.split("/folders/", 1)[1]
        value = value.split("?", 1)[0].split("/", 1)[0]
    return value


def folder_info(access_token, folder_id):
    url = DRIVE_API + "/files/" + urllib.parse.quote(folder_id) + "?" + urllib.parse.urlencode(
        {"fields": "id,name,mimeType,driveId", "supportsAllDrives": "true"}
    )
    request = urllib.request.Request(url, headers=auth_headers(access_token))

    try:
        with http(request) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = read_http_error(error)
        raise RuntimeError(
            "Cannot read UMP_DRIVE_FOLDER_ID (HTTP %s): %s" % (error.code, detail)
        ) from error


def escape_query(value):
    return value.replace("\\", "\\\\").replace("'", "\\'")


def list_files(access_token, query, fields, order_by=None, page_size=100):
    params = {
        "q": query,
        "fields": "files(" + fields + ")",
        "pageSize": str(page_size),
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "corpora": "allDrives",
    }
    if order_by:
        params["orderBy"] = order_by

    url = DRIVE_API + "/files?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=auth_headers(access_token))
    with http(request) as response:
        return json.loads(response.read().decode()).get("files", [])


def find_folder(access_token, parent_id, name):
    query = (
        "name = '%s' and mimeType = '%s' and '%s' in parents and trashed = false"
        % (escape_query(name), FOLDER_MIME, escape_query(parent_id))
    )
    files = list_files(access_token, query, "id,name", page_size=10)
    return files[0]["id"] if files else None


def create_folder(access_token, parent_id, name):
    metadata = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
    url = DRIVE_API + "/files?" + urllib.parse.urlencode(
        {"fields": "id,name", "supportsAllDrives": "true"}
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(metadata).encode(),
        method="POST",
        headers=auth_headers(
            access_token, {"Content-Type": "application/json; charset=UTF-8"}
        ),
    )
    with http(request) as response:
        return json.loads(response.read().decode())["id"]


def resolve_folder(access_token, root_id, sub_path):
    folder_id = root_id
    for name in [part.strip() for part in sub_path.split("/") if part.strip()]:
        existing = find_folder(access_token, folder_id, name)
        if existing:
            log("Drive folder: %s (existing)" % name)
            folder_id = existing
        else:
            folder_id = create_folder(access_token, folder_id, name)
            log("Drive folder: %s (created)" % name)
    return folder_id


def find_same_name_files(access_token, folder_id, file_name):
    query = (
        "name = '%s' and '%s' in parents and trashed = false"
        % (escape_query(file_name), escape_query(folder_id))
    )
    return list_files(
        access_token,
        query,
        "id,name,modifiedTime",
        order_by="modifiedTime desc",
        page_size=100,
    )


def trash_file(access_token, file_id):
    url = DRIVE_API + "/files/" + urllib.parse.quote(file_id) + "?" + urllib.parse.urlencode(
        {"supportsAllDrives": "true"}
    )
    request = urllib.request.Request(
        url,
        data=json.dumps({"trashed": True}).encode(),
        method="PATCH",
        headers=auth_headers(
            access_token, {"Content-Type": "application/json; charset=UTF-8"}
        ),
    )
    with http(request) as response:
        response.read()


def replacement_target(access_token, folder_id, file_name):
    existing = find_same_name_files(access_token, folder_id, file_name)
    if not existing:
        return None

    # Most recently modified copy is the canonical one. PATCHing it uploads a
    # new revision while preserving file id and any shared link.
    target_id = existing[0]["id"]
    log("Existing file found - uploading a new revision (same file id).")
    log("Existing File ID: " + target_id)

    extras = existing[1:]
    if not extras:
        return target_id

    if os.environ.get("UMP_DRIVE_KEEP_DUPLICATES", "").strip() == "1":
        log("Leaving %d older duplicate(s) in place." % len(extras))
        return target_id

    for duplicate in extras:
        try:
            trash_file(access_token, duplicate["id"])
            log("Moved older duplicate to trash: " + duplicate["id"])
        except urllib.error.HTTPError as error:
            log(
                "WARNING: cannot trash duplicate %s (HTTP %s)."
                % (duplicate["id"], error.code)
            )

    return target_id


def start_resumable_session(access_token, folder_id, file_name, file_size, file_id):
    if file_id:
        metadata = {"name": file_name}
        url = (
            DRIVE_UPLOAD_API
            + "/files/"
            + urllib.parse.quote(file_id)
            + "?"
            + urllib.parse.urlencode(
                {
                    "uploadType": "resumable",
                    "supportsAllDrives": "true",
                    "fields": "id,name,webViewLink",
                }
            )
        )
        method = "PATCH"
    else:
        metadata = {"name": file_name, "parents": [folder_id]}
        url = DRIVE_UPLOAD_API + "/files?" + urllib.parse.urlencode(
            {
                "uploadType": "resumable",
                "supportsAllDrives": "true",
                "fields": "id,name,webViewLink",
            }
        )
        method = "POST"

    request = urllib.request.Request(
        url,
        data=json.dumps(metadata).encode(),
        method=method,
        headers=auth_headers(
            access_token,
            {
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "application/octet-stream",
                "X-Upload-Content-Length": str(file_size),
            },
        ),
    )

    with http(request) as response:
        location = response.headers.get("Location")

    if not location:
        raise RuntimeError("Drive did not return a resumable session URI.")
    return location


def send_chunks(session_uri, access_token, file_path, file_size):
    sent = 0
    result = {}

    with open(file_path, "rb") as stream:
        while sent < file_size:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break

            last = sent + len(chunk) - 1
            request = urllib.request.Request(
                session_uri,
                data=chunk,
                method="PUT",
                headers=auth_headers(
                    access_token,
                    {
                        "Content-Length": str(len(chunk)),
                        "Content-Range": "bytes %d-%d/%d" % (sent, last, file_size),
                    },
                ),
            )

            try:
                with http(request) as response:
                    body = response.read().decode(errors="replace")
                    result = json.loads(body) if body else {}
                    sent = last + 1
                    log("Upload 100% - done")
                    break
            except urllib.error.HTTPError as error:
                if error.code != 308:
                    raise

                # Google accepted the chunk and expects the next range.
                range_header = error.headers.get("Range", "") if error.headers else ""
                if range_header and "-" in range_header:
                    try:
                        sent = int(range_header.rsplit("-", 1)[1]) + 1
                        stream.seek(sent)
                    except ValueError:
                        sent = last + 1
                else:
                    sent = last + 1

                percent = int(sent * 100 / file_size)
                log("Upload %d%%" % percent)

    return result


def report_upload(result, file_path, write_url_file):
    file_id = result.get("id", "")
    file_name = result.get("name", os.path.basename(file_path))
    url = result.get("webViewLink") or (
        "https://drive.google.com/file/d/" + file_id + "/view" if file_id else ""
    )

    log("Google Drive upload SUCCESS.")
    log("File ID: " + (file_id or "unknown"))
    log("File name: " + file_name)
    log("Drive URL: " + (url or "unknown"))

    # Keep Builds/ump_drive_url.txt pointing at the actual APK/AAB/IPA.
    # Telegram and post-build messages consume that file, so the optional
    # BUILD_INFO upload must never replace it with a text-file URL.
    if not write_url_file:
        return

    url_path = os.environ.get("UMP_DRIVE_URL_FILE", "Builds/ump_drive_url.txt")
    try:
        directory = os.path.dirname(url_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(url_path, "w", encoding="utf-8") as output:
            output.write("url=" + url + "\n")
            output.write("artifact=" + os.path.basename(file_path) + "\n")
    except Exception as error:
        log("WARNING: could not write %s: %s" % (url_path, error))


def read_key_value_file(path):
    values = {}
    if not path or not os.path.isfile(path):
        return values

    try:
        with open(path, "r", encoding="utf-8") as stream:
            for raw in stream:
                line = raw.strip()
                if not line or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    except (OSError, UnicodeError) as error:
        log("WARNING: cannot read build info %s: %s" % (path, error))

    return values


def build_info():
    path = os.environ.get("UMP_BUILD_INFO", "Builds/ump_build_info.txt")
    return read_key_value_file(path)


def game_name(info):
    name = os.environ.get("UMP_DRIVE_GAME_NAME", "").strip()
    if name:
        return name

    name = info.get("PRODUCT_NAME", "").strip()
    if name:
        return name

    job = os.environ.get("JOB_NAME", "").strip()
    return job.split("/")[0] if job else ""


def is_truthy(value):
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def sub_path(file_path, info):
    # iOS BUILD_INFO-only uploads always live in <Game>/IOS.
    # Keep this before UMP_DRIVE_SUBPATH so a machine/global override
    # cannot accidentally route iOS metadata into APK/AAB folders.
    if is_truthy(os.environ.get("UMP_DRIVE_BUILD_INFO_ONLY", "")):
        parts = [part for part in (game_name(info), "IOS") if part]
        return "/".join(parts)

    if "UMP_DRIVE_SUBPATH" in os.environ:
        return os.environ["UMP_DRIVE_SUBPATH"].strip()

    kinds = {".apk": "APK", ".aab": "AAB", ".ipa": "IPA"}
    kind = kinds.get(os.path.splitext(file_path)[1].lower(), "")
    parts = [part for part in (game_name(info), kind) if part]
    return "/".join(parts)


def safe_file_part(value):
    value = (value or "").strip()
    if not value:
        return ""
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("._-")


def find_companion_build_info(artifact, info):
    artifact_dir = os.path.abspath(os.path.dirname(artifact) or ".")
    search_dirs = [artifact_dir]

    builds_root = os.path.abspath("Builds")
    if builds_root not in search_dirs:
        search_dirs.append(builds_root)

    preferred = []
    for name in (info.get("PRODUCT_NAME_SAFE", ""), info.get("PRODUCT_NAME", ""), game_name(info)):
        name = (name or "").strip()
        if name:
            preferred.append(name + "_BUILD_INFO.txt")
            safe = safe_file_part(name)
            if safe:
                preferred.append(safe + "_BUILD_INFO.txt")

    # Preserve order while removing duplicates.
    seen = set()
    preferred = [x for x in preferred if not (x in seen or seen.add(x))]

    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        for file_name in preferred:
            candidate = os.path.join(directory, file_name)
            if os.path.isfile(candidate):
                return candidate

    # Fallback for projects that generate the conventional *_BUILD_INFO.txt
    # but sanitize the game name differently from UMP. Only auto-pick it when
    # the directory contains exactly one such file, so stale files cannot be
    # selected ambiguously.
    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        matches = sorted(
            os.path.join(directory, entry)
            for entry in os.listdir(directory)
            if entry.endswith("_BUILD_INFO.txt")
            and os.path.isfile(os.path.join(directory, entry))
        )
        if len(matches) == 1:
            return matches[0]

    return ""


def build_info_drive_name(local_path, info):
    companion = read_key_value_file(local_path)
    version = info.get("VERSION", "").strip() or companion.get("VERSION", "").strip()
    version = safe_file_part(version)

    base, ext = os.path.splitext(os.path.basename(local_path))
    ext = ext or ".txt"

    if not version:
        raise RuntimeError(
            "BUILD_INFO file found but VERSION is unavailable: " + local_path
        )

    version_label = version if version.lower().startswith("v") else "v" + version
    return "%s_%s%s" % (base, version_label, ext)


def upload(access_token, folder_id, file_path, remote_name=None, write_url_file=True):
    file_name = remote_name or os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    if file_size <= 0:
        raise RuntimeError("Artifact is empty: " + file_path)

    log("Uploading to Google Drive: " + file_name)
    if remote_name and remote_name != os.path.basename(file_path):
        log("Local file: " + file_path)
    log("File size: %d bytes" % file_size)

    target_id = replacement_target(access_token, folder_id, file_name)
    session_uri = start_resumable_session(
        access_token, folder_id, file_name, file_size, target_id
    )
    result = send_chunks(session_uri, access_token, file_path, file_size)
    report_upload(result, file_path, write_url_file)


def main():
    if len(sys.argv) < 2:
        raise RuntimeError("Missing artifact path.")

    artifact = sys.argv[1]
    if not os.path.isfile(artifact):
        raise RuntimeError("Artifact not found: " + artifact)

    root_id = folder_id_from_value(os.environ.get("UMP_DRIVE_FOLDER_ID", ""))
    if not root_id:
        raise RuntimeError("UMP_DRIVE_FOLDER_ID is empty.")

    access_token = oauth_access_token()
    info = folder_info(access_token, root_id)
    if info.get("mimeType") != FOLDER_MIME:
        raise RuntimeError("UMP_DRIVE_FOLDER_ID is not a Google Drive folder.")

    log(
        "Root folder: %s%s"
        % (
            info.get("name", root_id),
            " (Shared Drive)" if info.get("driveId") else " (My Drive)",
        )
    )

    info_values = build_info()

    target_folder = root_id
    path = sub_path(artifact, info_values)
    if path:
        log("Drive path: " + path)
        try:
            target_folder = resolve_folder(access_token, root_id, path)
        except urllib.error.HTTPError as error:
            detail = read_http_error(error)
            log(
                "WARNING: cannot create/resolve '%s' (HTTP %s). "
                "Uploading into root folder instead. %s"
                % (path, error.code, detail)
            )
            target_folder = root_id

    build_info_only = is_truthy(
        os.environ.get("UMP_DRIVE_BUILD_INFO_ONLY", "")
    )

    if build_info_only:
        if not os.path.basename(artifact).endswith("_BUILD_INFO.txt"):
            raise RuntimeError(
                "UMP_DRIVE_BUILD_INFO_ONLY requires a *_BUILD_INFO.txt file: "
                + artifact
            )
        log("Mode: iOS BUILD_INFO only")
        log("No IPA/app will be uploaded to Drive.")
        upload(
            access_token,
            target_folder,
            artifact,
            write_url_file=False,
        )
        return

    # Upload the game artifact first. This is still the canonical URL written
    # to Builds/ump_drive_url.txt and used by Telegram notifications.
    upload(access_token, target_folder, artifact)

    companion = find_companion_build_info(artifact, info_values)
    if companion:
        drive_name = build_info_drive_name(companion, info_values)
        log("Companion BUILD_INFO found: " + companion)
        log("Companion Drive name: " + drive_name)
        log("Companion destination: same Drive folder as artifact")
        upload(
            access_token,
            target_folder,
            companion,
            remote_name=drive_name,
            write_url_file=False,
        )
    else:
        log("Companion BUILD_INFO: not found - skipped (optional).")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        detail = read_http_error(error)
        log("Google Drive API ERROR (HTTP %s):" % error.code)
        if detail:
            print(detail, flush=True)
        sys.exit(1)
    except Exception as error:
        log("ERROR: " + str(error))
        sys.exit(1)
