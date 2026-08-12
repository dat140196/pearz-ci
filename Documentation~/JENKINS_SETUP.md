# UMP Jenkins Setup 1.2.0

Branches:
- release/android -> AAB
- release/android-test -> APK
- release/ios-test -> iOS Xcode project for device testing
- release/ios -> Archive/Export + TestFlight

Create a Multibranch Pipeline, connect the Git repository, use Jenkinsfile at project root, and optionally filter `release/(android|android-test|ios-test|ios)`.

## Unity path
Nothing to configure. `Jenkins/find_unity.sh` resolves the editor in this order:
1. `UNITY_PATH` (Jenkins env var) if it points to an executable
2. Unity Hub install matching `ProjectSettings/ProjectVersion.txt`
3. Newest Unity Hub install on the machine

Hub locations searched: `/Applications/Unity/Hub/Editor` and `~/Applications/Unity/Hub/Editor`.

## Telegram
Set Jenkins credentials (Secret text):
- UMP_TELEGRAM_BOT_TOKEN
- UMP_TELEGRAM_CHAT_ID

Status is sent on both SUCCESS and FAILURE. If an artifact exists and is <=50 MB, the artifact is also sent as a Telegram document. Larger artifacts are still uploaded to Drive and Telegram receives the status.

## Google Drive

Credentials (Secret text):
- `UMP_DRIVE_SERVICE_ACCOUNT_JSON` = the **contents** of the service-account JSON (a path to a JSON file on the Mac also works)
- `UMP_DRIVE_FOLDER_ID` = destination folder ID (a pasted folder URL is accepted)

Enable the Google Drive API on the service account's Google Cloud project.

### Important: service accounts have no storage quota

Sharing a normal My Drive folder with the service account is **not enough**. The upload fails with:

```
403 storageQuotaExceeded
Service Accounts do not have storage quota.
```

because the uploaded file would have to be owned by the service account, which owns no storage. Pick one of these:

**Option 1 - Shared Drive (recommended, needs Google Workspace)**
1. Google Drive -> Shared drives -> create a drive (e.g. `PEARZ Builds`)
2. Add the service-account email (`...@....iam.gserviceaccount.com`) as **Content manager**
3. Create the destination folder inside that Shared Drive
4. Put that folder's ID in `UMP_DRIVE_FOLDER_ID`

**Option 2 - Domain-wide delegation (Workspace admin)**
1. Admin console -> Security -> API controls -> Domain-wide delegation
2. Authorize the service-account client ID for scope `https://www.googleapis.com/auth/drive`
3. Add a Jenkins env var `UMP_DRIVE_IMPERSONATE_USER=user@yourdomain.com`

The upload then runs as that user and a normal My Drive folder works.

**Option 3 - OAuth refresh token (personal Gmail, no Workspace)**

Create an OAuth client (Desktop app), get a refresh token for scope `https://www.googleapis.com/auth/drive.file`, then set these Jenkins credentials instead of the service-account JSON:
- `UMP_DRIVE_OAUTH_CLIENT_ID`
- `UMP_DRIVE_OAUTH_CLIENT_SECRET`
- `UMP_DRIVE_OAUTH_REFRESH_TOKEN`

and bind them in the `Drive Upload` stage of the Jenkinsfile the same way the service-account credential is bound.

Uploads use the Drive v3 resumable flow in 8 MB chunks with `supportsAllDrives=true`, so large APK/AAB/IPA files stream instead of being buffered whole. A failed Drive upload never fails the Jenkins build.

## iOS
Configure Xcode signing on the Jenkins Mac and verify manual Archive/Export/Upload before CI. No Apple password is stored in UMP. The Xcode scheme is read from the generated project; set `IOS_SCHEME` in Jenkins only to override it.
