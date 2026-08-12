# UMP Unity Mobile Pipeline 1.12.4

Install using Unity Package Manager -> Add package from Git URL.

**Pin the version.** An unpinned git URL makes Unity contact GitHub on
every single build to check whether the branch moved, so a network hiccup
aborts the build with `Project has invalid dependencies`. Add `#<tag>` in
`Packages/manifest.json`:

```json
"com.ump.pearz-build-pipeline": "https://github.com/dat140196/pearz-ci.git#1.12.2"
```

Unity then locks that revision in `packages-lock.json` and reuses its
cache. Change the tag when you want the update.

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

Android signing needs no credential: commit the key as
`Keystores/<package-name>.keystore` + `.properties` in the game repo
(see JENKINS_SETUP.md).

## 1.12.4
- Prefer the team of the Apple ID signed in to Xcode over a certificate
  found in the keychain, and warn when the team being forced is not one
  the account belongs to - that mismatch fails as "No profiles for ...",
  which reads like a missing account.

## 1.12.3
- On a signing failure the log now prints the build user, whether an
  Xcode account token is visible from the Jenkins session, the keychain
  search list and the profile count - enough to tell "no account" apart
  from "locked keychain" without another build.

## 1.12.2
- The "no Apple ID signed in" check is a hint, not a gate: where Xcode
  records accounts varies by version, so the build always runs and the
  signing guidance is printed from xcodebuild's own error instead.

## 1.12.1
- Detect "certificate present but no Apple ID signed in to Xcode" before
  building, and support an App Store Connect API key
  (`UMP_ASC_KEY_PATH` / `_KEY_ID` / `_ISSUER_ID`) for headless signing.

## 1.12.0
- The iOS Xcode project is exported to `Builds/iOS/<Game name>/`, and the
  scripts find the `.xcodeproj` instead of assuming a fixed path.
- The signing team is taken from `UMP_IOS_TEAM_ID`, then Player Settings,
  then the Apple Development certificate on the Mac. Missing team now
  stops the stage with instructions.

## 1.11.2
- Pick the `Unity-iPhone` scheme instead of the first one listed.
  `GameAssembly` sorts first and only builds the IL2CPP static library,
  so the install stage found no `.app`. Same fix in `archive_ios.sh`.

## 1.11.0
- `release/ios-test` now really installs on the device attached to the
  Jenkins Mac: xcodebuild compiles the generated Xcode project for that
  device and `devicectl` (or `ios-deploy`) installs and launches it.
  Before, the stage only produced an Xcode project and reported SUCCESS.

## 1.10.0
- Drive upload overwrites a file of the same name in the same folder
  (new revision, same id and link) instead of adding another copy, and
  trashes duplicates left by earlier builds
  (`UMP_DRIVE_KEEP_DUPLICATES=1` to keep them).

## 1.9.0
- Keystore passwords from a `.properties` file are passed to Unity in a
  600 temp file, not in the environment: Unity dumps all environment
  variables into the log when Gradle fails, and Jenkins cannot mask a
  value it never issued.

## 1.8.0
- Keystores are read from `Keystores/<package-name>.keystore` in the game
  repo first, then from `~/.pearz/keystores`, then from job credentials.
  A new project only needs a git push.

## 1.7.0
- Keystores are resolved per project from `~/.pearz/keystores` by
  applicationIdentifier, so several games share one Jenkins without one
  set of credentials each. Jenkins credentials still override it.

## 1.6.0
- Android release signing from Jenkins credentials
  (`UMP_ANDROID_KEYSTORE` + pass/alias). Unity never creates a release
  keystore and does not keep passwords in the project, so a batchmode
  build cannot sign without them. The AAB build now fails instead of
  silently producing a debug-signed bundle Google Play would reject;
  the test APK still falls back to the debug key.

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
