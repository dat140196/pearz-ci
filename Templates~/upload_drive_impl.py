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
#   UMP_DRIVE_FOLDER_ID
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


def start_session(access_token, folder_id, file_name, file_size):

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

    request = urllib.request.Request(
        url,
        data=json.dumps(metadata).encode(),
        method="POST",
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


def upload(access_token, folder_id, file_path, using_service_account):

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    log("Uploading to Google Drive: " + file_name)
    log("File size: " + str(file_size) + " bytes")

    info = folder_info(access_token, folder_id)

    if info is not None:

        log(
            "Destination folder: " + str(info.get("name")) +
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

    try:

        session_uri = start_session(
            access_token,
            folder_id,
            file_name,
            file_size
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

    log(
        "Drive URL: " + (
            result.get("webViewLink") or
            "https://drive.google.com/file/d/" + file_id + "/view"
        )
    )


# ============================================================
# ENTRY
# ============================================================

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

    upload(
        access_token,
        folder_id,
        artifact,
        using_service_account
    )
