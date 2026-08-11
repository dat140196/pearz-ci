#!/usr/bin/env python3

import os
import sys
import json
import time
import base64
import hashlib
import urllib.request
import urllib.parse


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def token(service_account_json):

    # Jenkins Credential contains the JSON directly,
    # not a file path.
    sa = json.loads(service_account_json)

    now = int(time.time())

    header = {
        "alg": "RS256",
        "typ": "JWT"
    }

    claim = {
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/drive.file",
        "aud": sa["token_uri"],
        "iat": now,
        "exp": now + 3600
    }

    header_b64 = b64(
        json.dumps(
            header,
            separators=(",", ":")
        ).encode()
    )

    claim_b64 = b64(
        json.dumps(
            claim,
            separators=(",", ":")
        ).encode()
    )

    unsigned = (
        header_b64 +
        "." +
        claim_b64
    ).encode()

    # Use openssl to sign JWT with the private key.
    import subprocess

    private_key = sa["private_key"]

    proc = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-sign",
            "/dev/stdin"
        ],
        input=unsigned,
        capture_output=True
    )

    # openssl cannot reliably receive the private key this way
    # on all macOS versions, so create a temporary secure file.
    import tempfile

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

        signature = b64(proc.stdout)

    assertion = (
        header_b64 +
        "." +
        claim_b64 +
        "." +
        signature
    )

    body = urllib.parse.urlencode({
        "grant_type":
            "urn:ietf:params:oauth:grant-type:jwt-bearer",

        "assertion":
            assertion
    }).encode()

    request = urllib.request.Request(
        sa["token_uri"],
        data=body,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        }
    )

    with urllib.request.urlopen(request) as response:

        data = json.loads(
            response.read().decode()
        )

    return data["access_token"]


def upload(access_token, folder_id, file_path):

    file_name = os.path.basename(file_path)

    file_size = os.path.getsize(file_path)

    print(
        f"[PEARZ] Uploading to Google Drive: "
        f"{file_name}"
    )

    print(
        f"[PEARZ] File size: "
        f"{file_size} bytes"
    )

    metadata = {
        "name": file_name,
        "parents": [
            folder_id
        ]
    }

    boundary = (
        "-------PEARZDriveBoundary"
        + hashlib.md5(
            str(time.time()).encode()
        ).hexdigest()
    )

    metadata_bytes = json.dumps(
        metadata
    ).encode()

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = bytearray()

    body.extend(
        (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n"
            "\r\n"
        ).encode()
    )

    body.extend(metadata_bytes)

    body.extend(
        (
            "\r\n"
            f"--{boundary}\r\n"
            "Content-Type: application/octet-stream\r\n"
            "\r\n"
        ).encode()
    )

    body.extend(file_bytes)

    body.extend(
        (
            "\r\n"
            f"--{boundary}--\r\n"
        ).encode()
    )

    url = (
        "https://www.googleapis.com/"
        "upload/drive/v3/files"
        "?uploadType=multipart"
    )

    request = urllib.request.Request(
        url,
        data=bytes(body),
        method="POST",
        headers={
            "Authorization":
                f"Bearer {access_token}",

            "Content-Type":
                f"multipart/related; boundary={boundary}"
        }
    )

    try:

        with urllib.request.urlopen(request) as response:

            response_data = response.read().decode()

            result = json.loads(
                response_data
            )

            print(
                "[PEARZ] Google Drive upload SUCCESS."
            )

            print(
                "[PEARZ] File ID: "
                + result.get("id", "unknown")
            )

            print(
                "[PEARZ] File name: "
                + result.get("name", file_name)
            )

            print(
                "[PEARZ] Drive URL: "
                "https://drive.google.com/file/d/"
                + result.get("id", "")
                + "/view"
            )

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            errors="replace"
        )

        print(
            "[PEARZ] Google Drive API ERROR:"
        )

        print(error_body)

        raise


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "[PEARZ] ERROR: "
            "missing artifact path."
        )

        sys.exit(1)

    service_account_json = os.environ.get(
        "UMP_DRIVE_SERVICE_ACCOUNT_JSON",
        ""
    )

    folder_id = os.environ.get(
        "UMP_DRIVE_FOLDER_ID",
        ""
    )

    artifact = sys.argv[1]

    if not service_account_json:

        print(
            "[PEARZ] ERROR: "
            "UMP_DRIVE_SERVICE_ACCOUNT_JSON "
            "is empty."
        )

        sys.exit(1)

    if not folder_id:

        print(
            "[PEARZ] ERROR: "
            "UMP_DRIVE_FOLDER_ID "
            "is empty."
        )

        sys.exit(1)

    if not os.path.isfile(artifact):

        print(
            "[PEARZ] ERROR: "
            f"Artifact not found: {artifact}"
        )

        sys.exit(1)

    access_token = token(
        service_account_json
    )

    upload(
        access_token,
        folder_id,
        artifact
    )