# UMP Unity Mobile Pipeline 1.2.0

Install using Unity Package Manager -> Add package from Git URL.

After import, use:

Tools > UMP > Setup / Sync Jenkins Files -> **Sync UMP Files**

No Unity path to fill in: the build machine resolves Unity itself
(`Jenkins/find_unity.sh`) from `ProjectSettings/ProjectVersion.txt`,
then from Unity Hub. Set `UNITY_PATH` in Jenkins only to override it.

Branches:
- release/android -> AAB
- release/android-test -> APK
- release/ios-test -> iOS Xcode project
- release/ios -> Archive/Export/TestFlight

Jenkins credentials (Secret text):
- UMP_DRIVE_SERVICE_ACCOUNT_JSON (the service-account JSON itself)
- UMP_DRIVE_FOLDER_ID
- UMP_TELEGRAM_BOT_TOKEN
- UMP_TELEGRAM_CHAT_ID

## 1.2.0
- Drive upload uses resumable upload + `supportsAllDrives`, so it works
  with Shared Drives. A service account has no storage quota of its own,
  so the destination folder must be in a Shared Drive, or you must use
  impersonation / an OAuth refresh token. See `Documentation~/JENKINS_SETUP.md`.
- Unity is auto-detected; the Unity path and iOS scheme fields are gone.
- iOS scheme is read from the generated Xcode project.
