# UMP Unity Mobile Pipeline 1.5.0

Install using Unity Package Manager -> Add package from Git URL.

The Jenkinsfile and the `Jenkins/` scripts are written into the project
**automatically** when the package is installed or updated - nothing to click.

To force a sync (e.g. after editing the generated files by hand):

**Pearz > SetupJenkin** -> `Force Sync UMP Files`

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

## 1.5.0
- Builds start on push: `pollSCM` trigger in the Jenkinsfile, plus
  `disableConcurrentBuilds()` and log rotation. Non-release branches end
  as NOT_BUILT instead of failing, with no Telegram spam.

## 1.4.0
- Files sync automatically on install/update (signature of the package
  version + templates is cached in `Library/UMP.sync`). Skipped in
  batch mode so Jenkins builds never rewrite the workspace.
- Menu moved to **Pearz > SetupJenkin**; the button is now a manual
  fallback.
- Unchanged files are no longer rewritten, so Unity does not reimport
  `JenkinsBuild.cs` on every sync.

## 1.3.0
- Artifacts are named `ProductName-vVersion` from Player Settings
  (e.g. `MeowPuzzle-v1.0.0.apk`).
- Drive uploads go to `<root>/<Game name>/<APK|AAB>/`, folders created
  automatically.
- Drive upload runs on Android branches only; iOS uses TestFlight /
  direct install.
- `release/android` now really produces an AAB (`buildAppBundle` was
  never enabled).

## 1.2.0
- Drive upload uses resumable upload + `supportsAllDrives`, so it works
  with Shared Drives. A service account has no storage quota of its own,
  so the destination folder must be in a Shared Drive, or you must use
  impersonation / an OAuth refresh token. See `Documentation~/JENKINS_SETUP.md`.
- Unity is auto-detected; the Unity path and iOS scheme fields are gone.
- iOS scheme is read from the generated Xcode project.
