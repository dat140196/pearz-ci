# UMP Jenkins Setup 1.0.0

Branches:
- release/android -> AAB
- release/android-test -> APK
- release/ios-test -> iOS Xcode project for device testing
- release/ios -> Archive/Export + TestFlight

Create a Multibranch Pipeline, connect the Git repository, use Jenkinsfile at project root, and optionally filter `release/(android|android-test|ios-test|ios)`.

## Telegram
Set Jenkins environment/credentials:
- UMP_TELEGRAM_BOT_TOKEN
- UMP_TELEGRAM_CHAT_ID

Status is sent on both SUCCESS and FAILURE. If an artifact exists and is <=50 MB, the artifact is also sent as a Telegram document. Larger artifacts are still uploaded to Drive and Telegram receives the status.

## Google Drive
Set:
- UMP_DRIVE_SERVICE_ACCOUNT_JSON = absolute path to a Google service-account JSON on the Jenkins Mac
- UMP_DRIVE_FOLDER_ID = destination Drive folder ID

Share the destination Drive folder with the service-account email. Do not commit the JSON. UMP uses the Google Drive API resumable upload flow.

## iOS
Configure Xcode signing on the Jenkins Mac and verify manual Archive/Export/Upload before CI. No Apple password is stored in UMP.
