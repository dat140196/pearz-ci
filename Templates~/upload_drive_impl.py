#!/usr/bin/env python3

# ============================================================
# PEARZ / UMP Google Drive upload
#
# Auth (choose ONE):
#
#   1. Service account  ->  UMP_DRIVE_SERVICE_ACCOUNT_JSON
#      The destination folder MUST live in a Shared Drive
#      ("Drive dùng chung"), because service accounts have
#      NO storage quota of their own.
#      Optional: UMP_DRIVE_IMPERSONATE_USER (domain-wide
#      delegation) to upload as a real Workspace user, which
#      also works for a normal My Drive folder.
#
#   2. OAuth refresh token (no Workspace / no Shared Drive)
#      UMP_DRIVE_OAUTH_CLIENT_ID
#      UMP_DRIVE_OAUTH_CLIENT_SECRET
#      UMP_DRIVE_OAUTH_REFRESH_TOKEN
#
# Destination:
#   UMP_DRIVE_FOLDER_ID   root folder / Shared Drive folder
#
#   Files are placed in  <root>/<Game name>/<APK|AAB>/file
#   Game name comes from Builds/ump_build_info.txt (written by
#   JenkinsBuild), or UMP_DRIVE_GAME_NAME, or JOB_NAME.
#   UMP_DRIVE_SUBPATH overrides the whole sub path.
#   UMP_DRIVE_SUBPATH="" uploads straight into the root folder.
#
#   A file with the same name in the same folder is overwritten
#   (new revision, same id and link). Older duplicates left by
#   previous builds are moved to the trash unless
#   UMP_DRIVE_KEEP_DUPLICATES=1.
# ============================================================

import os
import sys
import json
import time
import base64
import tempfile
import subprocess
import urllib.request
import urllib.parse
import urllib.error


SCOPE = "https://www.googleapis.com/auth/drive"

CHUNK_SIZE = 8 * 1024 * 1024  # must stay a multiple of 256 KB

TOKEN_URI = "https://oauth2.googleapis.com/token"


def log(message):
    print("[PEARZ] " + message, flush=True)


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def opener():

    # Google answers resumable chunks with 308, which urllib
    # would otherwise try to follow as a redirect.

    class NoRedirect(urllib.request.HTTPRedirectHandler):

        def redirect_request(self, *args, **kwargs):
            return None

    return urllib.request.build_opener(NoRedirect)


def http(request):
    return opener().open(request)


# ============================================================
# AUTH
# ============================================================

def sign_jwt(private_key, unsigned):

    with tempfile.NamedTemporaryFile(
        mode="w",
        delete=True,
        prefix="pearz-sa-",
        suffix=".pem"
    ) as key_file:

        key_file.write(private_key)
        key_file.flush()

        proc = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                key_file.name
            ],
            input=unsigned,
            capture_output=True
        )

        if proc.returncode != 0:

            raise RuntimeError(
                "OpenSSL signing failed: " +
                proc.stderr.decode(errors="replace")
            )

        return b64(proc.stdout)


def token_from_service_account(service_account_json, subject):

    # The Jenkins credential holds the JSON itself,
    # not a path to a file.

    sa = json.loads(service_account_json)

    now = int(time.time())

    token_uri = sa.get("token_uri", TOKEN_URI)

    header = {
        "alg": "RS256",
        "typ": "JWT"
    }

    claim = {
        "iss": sa["client_email"],
        "scope": SCOPE,
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600
    }

    if subject:
        claim["sub"] = subject

    header_b64 = b64(
        json.dumps(header, separators=(",", ":")).encode()
    )

    claim_b64 = b64(
        json.dumps(claim, separators=(",", ":")).encode()
    )

    unsigned = (header_b64 + "." + claim_b64).encode()

    assertion = (
        header_b64 +
        "." +
        claim_b64 +
        "." +
        sign_jwt(sa["private_key"], unsigned)
    )

    body = urllib.parse.urlencode({

        "grant_type":
            "urn:ietf:params:oauth:grant-type:jwt-bearer",

        "assertion":
            assertion

    }).encode()

    request = urllib.request.Request(
        token_uri,
        data=body,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        }
    )

    log("Auth: service account " + sa["client_email"])

    if subject:
        log("Auth: impersonating " + subject)

    with http(request) as response:
        return json.loads(response.read().decode())["access_token"]


def token_from_refresh_token(client_id, client_secret, refresh_token):

    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }).encode()

    request = urllib.request.Request(
        TOKEN_URI,
        data=body,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        }
    )

    log("Auth: OAuth refresh token")

    with http(request) as response:
        return json.loads(response.read().decode())["access_token"]


# ============================================================
# DRIVE
# ============================================================

def folder_info(access_token, folder_id):

    url = (
        "https://www.googleapis.com/drive/v3/files/" +
        urllib.parse.quote(folder_id) +
        "?" +
        urllib.parse.urlencode({
            "fields": "id,name,mimeType,driveId",
            "supportsAllDrives": "true"
        })
    )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + access_token
        }
    )

    try:

        with http(request) as response:
            return json.loads(response.read().decode())

    except urllib.error.HTTPError as e:

        log(
            "WARNING: cannot read destination folder "
            "(HTTP " + str(e.code) + "). "
            "Make sure the folder is shared with the "
            "upload identity."
        )

        return None


def escape_query(value):
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_folder(access_token, parent_id, name):

    query = (
        "name = '" + escape_query(name) + "' and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        "'" + escape_query(parent_id) + "' in parents and "
        "trashed = false"
    )

    url = (
        "https://www.googleapis.com/drive/v3/files?" +
        urllib.parse.urlencode({
            "q": query,
            "fields": "files(id,name)",
            "pageSize": "10",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "allDrives"
        })
    )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + access_token
        }
    )

    with http(request) as response:

        files = json.loads(response.read().decode()).get("files", [])

    return files[0]["id"] if files else None


def create_folder(access_token, parent_id, name):

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id]
    }

    url = (
        "https://www.googleapis.com/drive/v3/files?" +
        urllib.parse.urlencode({
            "fields": "id,name",
            "supportsAllDrives": "true"
        })
    )

    request = urllib.request.Request(
        url,
        data=json.dumps(metadata).encode(),
        method="POST",
        headers={

            "Authorization":
                "Bearer " + access_token,

            "Content-Type":
                "application/json; charset=UTF-8"
        }
    )

    with http(request) as response:
        return json.loads(response.read().decode())["id"]


def resolve_folder(access_token, root_id, sub_path):

    folder_id = root_id

    for name in [p.strip() for p in sub_path.split("/") if p.strip()]:

        existing = find_folder(access_token, folder_id, name)

        if existing:

            log("Drive folder: " + name + " (existing)")

            folder_id = existing

        else:

            folder_id = create_folder(access_token, folder_id, name)

            log("Drive folder: " + name + " (created)")

    return folder_id


def quota_help(using_service_account, info):

    print("")
    log("HOW TO FIX")
    log("Service accounts have no Drive storage quota, so")
    log("they cannot own files in a personal My Drive folder.")
    print("")
    log("Option 1 (recommended) - Shared Drive:")
    log("  1. Google Drive -> Shared drives -> create a drive")
    log("  2. Add the service-account email as Content manager")
    log("  3. Create the destination folder inside that drive")
    log("  4. Put that folder ID in UMP_DRIVE_FOLDER_ID")
    print("")
    log("Option 2 - Workspace domain-wide delegation:")
    log("  Authorize the service-account client ID for scope")
    log("  " + SCOPE + " in the Admin console, then set")
    log("  UMP_DRIVE_IMPERSONATE_USER=user@yourdomain.com")
    print("")
    log("Option 3 - personal Gmail (no Workspace):")
    log("  Use an OAuth client and set")
    log("  UMP_DRIVE_OAUTH_CLIENT_ID,")
    log("  UMP_DRIVE_OAUTH_CLIENT_SECRET,")
    log("  UMP_DRIVE_OAUTH_REFRESH_TOKEN")
    print("")

    if using_service_account and info is not None and not info.get("driveId"):

        log(
            "Detected: folder '" + str(info.get("name")) +
            "' is NOT in a Shared Drive."
        )


def find_files(access_token, folder_id, name):

    query = (
        "name = '" + escape_query(name) + "' and "
        "'" + escape_query(folder_id) + "' in parents and "
        "trashed = false"
    )

    url = (
        "https://www.googleapis.com/drive/v3/files?" +
        urllib.parse.urlencode({
            "q": query,
            "fields": "files(id,name,modifiedTime)",
            "orderBy": "modifiedTime desc",
            "pageSize": "100",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "allDrives"
        })
    )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + access_token
        }
    )

    try:

        with http(request) as response:
            return json.loads(response.read().decode()).get("files", [])

    except urllib.error.HTTPError as e:

        log(
            "WARNING: cannot list existing files "
            "(HTTP " + str(e.code) + "). Uploading as a new file."
        )

        return []


def trash_file(access_token, file_id):

    url = (
        "https://www.googleapis.com/drive/v3/files/" +
        urllib.parse.quote(file_id) +
        "?" +
        urllib.parse.urlencode({"supportsAllDrives": "true"})
    )

    request = urllib.request.Request(
        url,
        data=json.dumps({"trashed": True}).encode(),
        method="PATCH",
        headers={

            "Authorization":
                "Bearer " + access_token,

            "Content-Type":
                "application/json; charset=UTF-8"
        }
    )

    with http(request) as response:
        response.read()


# Same name in the same folder = same build. Overwrite it instead of
# piling up copies; the Drive link stays valid for whoever has it.
def replace_target(access_token, folder_id, file_name):

    existing = find_files(access_token, folder_id, file_name)

    if not existing:
        return None

    target = existing[0]["id"]

    log("Existing file found - uploading a new revision.")

    extras = existing[1:]

    if not extras:
        return target

    if os.environ.get("UMP_DRIVE_KEEP_DUPLICATES", "").strip() == "1":

        log(
            "Leaving " + str(len(extras)) +
            " older duplicate(s) in place."
        )

        return target

    for duplicate in extras:

        try:

            trash_file(access_token, duplicate["id"])

            log("Moved older duplicate to trash: " + duplicate["id"])

        except urllib.error.HTTPError as e:

            log(
                "WARNING: cannot trash duplicate " +
                duplicate["id"] + " (HTTP " + str(e.code) + ")."
            )

    return target


def start_session(access_token, folder_id, file_name, file_size, file_id):

    if file_id:

        # Updating keeps the same file id, so the shared link and
        # the Drive history survive.
        metadata = {"name": file_name}

        url = (
            "https://www.googleapis.com/upload/drive/v3/files/" +
            urllib.parse.quote(file_id) + "?" +
            urllib.parse.urlencode({
                "uploadType": "resumable",
                "supportsAllDrives": "true",
                "fields": "id,name,webViewLink"
            })
        )

        method = "PATCH"

    else:

        metadata = {
            "name": file_name,
            "parents": [folder_id]
        }

        url = (
            "https://www.googleapis.com/upload/drive/v3/files?" +
            urllib.parse.urlencode({
                "uploadType": "resumable",
                "supportsAllDrives": "true",
                "fields": "id,name,webViewLink"
            })
        )

        method = "POST"

    request = urllib.request.Request(
        url,
        data=json.dumps(metadata).encode(),
        method=method,
        headers={

            "Authorization":
                "Bearer " + access_token,

            "Content-Type":
                "application/json; charset=UTF-8",

            "X-Upload-Content-Type":
                "application/octet-stream",

            "X-Upload-Content-Length":
                str(file_size)
        }
    )

    with http(request) as response:

        location = response.headers.get("Location")

        if not location:

            raise RuntimeError(
                "Drive did not return a resumable session URI."
            )

        return location


def send_chunks(session_uri, access_token, file_path, file_size):

    sent = 0

    with open(file_path, "rb") as f:

        while sent < file_size:

            chunk = f.read(CHUNK_SIZE)

            if not chunk:
                break

            last = sent + len(chunk) - 1

            request = urllib.request.Request(
                session_uri,
                data=chunk,
                method="PUT",
                headers={

                    "Authorization":
                        "Bearer " + access_token,

                    "Content-Length":
                        str(len(chunk)),

                    "Content-Range":
                        "bytes " +
                        str(sent) + "-" + str(last) +
                        "/" + str(file_size)
                }
            )

            try:

                with http(request) as response:

                    body = response.read().decode(errors="replace")

                    percent = int((last + 1) * 100 / file_size)

                    log("Upload " + str(percent) + "% - done")

                    return json.loads(body) if body else {}

            except urllib.error.HTTPError as e:

                if e.code != 308:
                    raise

                # 308 = chunk accepted, keep going.

                sent = last + 1

                percent = int(sent * 100 / file_size)

                log("Upload " + str(percent) + "%")

    return {}


def upload(access_token, folder_id, file_path, using_service_account, info):

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    log("Uploading to Google Drive: " + file_name)
    log("File size: " + str(file_size) + " bytes")

    try:

        session_uri = start_session(
            access_token,
            folder_id,
            file_name,
            file_size,
            replace_target(access_token, folder_id, file_name)
        )

        result = send_chunks(
            session_uri,
            access_token,
            file_path,
            file_size
        )

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(errors="replace")

        log("Google Drive API ERROR (HTTP " + str(e.code) + "):")

        print(error_body)

        if "storageQuotaExceeded" in error_body:
            quota_help(using_service_account, info)

        raise

    file_id = result.get("id", "")

    log("Google Drive upload SUCCESS.")
    log("File ID: " + (file_id or "unknown"))
    log("File name: " + result.get("name", file_name))

    url = (
        result.get("webViewLink") or
        "https://drive.google.com/file/d/" + file_id + "/view"
    )

    log("Drive URL: " + url)

    # The Telegram notification runs in a later step, in another
    # process, so the link is left where it can pick it up. The
    # artifact name goes with it: the workspace survives between
    # builds and a stale link must not be reported as this one.
    url_path = os.environ.get(
        "UMP_DRIVE_URL_FILE",
        "Builds/ump_drive_url.txt"
    )

    try:

        directory = os.path.dirname(url_path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(url_path, "w") as f:
            f.write("url=" + url + "\n")
            f.write("artifact=" + os.path.basename(file_path) + "\n")

    except Exception as e:

        log("Could not write " + url_path + ": " + str(e))


# ============================================================
# ENTRY
# ============================================================

def build_info():

    path = os.environ.get(
        "UMP_BUILD_INFO",
        "Builds/ump_build_info.txt"
    )

    values = {}

    if not os.path.isfile(path):
        return values

    with open(path, "r") as f:

        for line in f:

            line = line.strip()

            if not line or "=" not in line:
                continue

            key, value = line.split("=", 1)

            values[key.strip()] = value.strip()

    return values


def game_name(info):

    name = os.environ.get("UMP_DRIVE_GAME_NAME", "").strip()

    if name:
        return name

    name = info.get("PRODUCT_NAME", "").strip()

    if name:
        return name

    # Multibranch job names look like "MeowPuzzle/release%2Fandroid".

    job = os.environ.get("JOB_NAME", "").strip()

    return job.split("/")[0] if job else ""


def sub_path(file_path):

    # An explicit value always wins, including an empty one
    # (upload straight into the root folder).

    if "UMP_DRIVE_SUBPATH" in os.environ:
        return os.environ["UMP_DRIVE_SUBPATH"].strip()

    kinds = {
        ".apk": "APK",
        ".aab": "AAB",
        ".ipa": "IPA"
    }

    kind = kinds.get(os.path.splitext(file_path)[1].lower(), "")

    parts = [p for p in [game_name(build_info()), kind] if p]

    return "/".join(parts)


def resolve_token():

    client_id = os.environ.get("UMP_DRIVE_OAUTH_CLIENT_ID", "").strip()

    client_secret = os.environ.get(
        "UMP_DRIVE_OAUTH_CLIENT_SECRET", ""
    ).strip()

    refresh_token = os.environ.get(
        "UMP_DRIVE_OAUTH_REFRESH_TOKEN", ""
    ).strip()

    if client_id and client_secret and refresh_token:

        return token_from_refresh_token(
            client_id,
            client_secret,
            refresh_token
        ), False

    service_account_json = os.environ.get(
        "UMP_DRIVE_SERVICE_ACCOUNT_JSON", ""
    ).strip()

    if not service_account_json:

        log(
            "ERROR: no Drive credential. Set "
            "UMP_DRIVE_SERVICE_ACCOUNT_JSON or the "
            "UMP_DRIVE_OAUTH_* variables."
        )

        sys.exit(1)

    # Accept a path to the JSON as well as the JSON itself.

    if os.path.isfile(service_account_json):

        with open(service_account_json, "r") as f:
            service_account_json = f.read()

    subject = os.environ.get(
        "UMP_DRIVE_IMPERSONATE_USER", ""
    ).strip()

    return token_from_service_account(
        service_account_json,
        subject
    ), True


if __name__ == "__main__":

    if len(sys.argv) < 2:

        log("ERROR: missing artifact path.")
        sys.exit(1)

    artifact = sys.argv[1]

    folder_id = os.environ.get("UMP_DRIVE_FOLDER_ID", "").strip()

    # Accept a pasted folder URL, not only the raw ID.

    if "/folders/" in folder_id:

        folder_id = folder_id.split("/folders/")[1]
        folder_id = folder_id.split("?")[0].split("/")[0]

    if not folder_id:

        log("ERROR: UMP_DRIVE_FOLDER_ID is empty.")
        sys.exit(1)

    if not os.path.isfile(artifact):

        log("ERROR: Artifact not found: " + artifact)
        sys.exit(1)

    access_token, using_service_account = resolve_token()

    info = folder_info(access_token, folder_id)

    if info is not None:

        log(
            "Root folder: " + str(info.get("name")) +
            (
                " (Shared Drive)"
                if info.get("driveId")
                else " (My Drive)"
            )
        )

        if using_service_account and not info.get("driveId"):

            log(
                "WARNING: folder is not in a Shared Drive - "
                "a service account cannot own files there."
            )

    target = folder_id

    path = sub_path(artifact)

    if path:

        log("Drive path: " + path)

        try:

            target = resolve_folder(access_token, folder_id, path)

        except urllib.error.HTTPError as e:

            log(
                "WARNING: cannot create '" + path + "' "
                "(HTTP " + str(e.code) + "). "
                "Uploading into the root folder instead."
            )

            target = folder_id

    upload(
        access_token,
        target,
        artifact,
        using_service_account,
        info
    )
