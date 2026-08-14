# Pearz Unity Mobile Pipeline

Pearz Unity Mobile Pipeline for Jenkins Android/iOS builds, TestFlight, Google Drive artifact upload, Telegram notifications, Android release signing, iOS device deployment, and SSH Git submodules.

## Install

Install with Unity Package Manager using **Add package from Git URL**:

```text
https://github.com/dat140196/pearz-ci.git#1.0.9
```

Pin the package version/tag in `Packages/manifest.json` so Unity does not have to follow a moving Git revision on every build:

```json
{
  "dependencies": {
    "com.ump.pearz-build-pipeline": "https://github.com/dat140196/pearz-ci.git#1.0.9"
  }
}
```

Unity stores the resolved revision in `Packages/packages-lock.json`. Update the tag when you intentionally upgrade UMP.

## Generated Jenkins files

UMP templates are the source of truth. In a normal Unity Editor session, installing/updating the package or running the setup sync writes the generated build files into the game project.

To force a sync:

```text
Pearz > SetupJenkin > Sync
```

Important: Jenkins runs Unity in `-batchmode`. UMP auto-sync is intentionally skipped in batch mode, so after updating the UMP package you must open/sync the project in Unity and commit the regenerated files to the game repository before Jenkins can use the new pipeline version.

Typical generated files include:

```text
Jenkinsfile
Assets/Editor/JenkinsBuild.cs
Jenkins/build_android.sh
Jenkins/build_ios.sh
Jenkins/find_unity.sh
Jenkins/resolve_keystore.sh
Jenkins/strip_ios_iap.sh
Jenkins/install_ios_device.sh
Jenkins/upload_drive.sh
Jenkins/upload_drive_impl.py
Jenkins/notify_telegram.sh
```

Every generated build script prints the UMP version in Jenkins logs. If the log shows an older UMP version than the package, sync again in Unity and commit the generated files.

## Branch rules

| Branch | Build | Signing / upload behavior |
|---|---|---|
| `release/android` | Android `.aab` | Release keystore required, then Google Drive upload |
| `release/android-test` | Android `.apk` | Custom/release keystore skipped, then Google Drive upload |
| `release/ios-test` | Xcode project + direct device install | CocoaPods workspace build; Firebase OFF strips APNs + Crashlytics build phase; then Drive BUILD_INFO upload |
| `release/ios` | Archive / Export / TestFlight | Production iOS flow, CocoaPods workspace archive when needed, then Drive BUILD_INFO upload |

Any other branch is rejected by the pipeline validation stage.

## Jenkins credentials

Create the following credentials only for the features you use.

### Git / submodules

```text
ID: github-ssh
Kind: SSH Username with private key
```

The SSH key must be able to clone every private Git submodule used by the Unity project.

The Jenkins **SSH Agent plugin is not required**. UMP binds the `github-ssh` private key with `sshUserPrivateKey` and passes it to Git through `GIT_SSH_COMMAND`.

### Android release signing (`release/android` only)

Optional Jenkins credentials:

```text
UMP_ANDROID_KEYSTORE           File
UMP_ANDROID_KEYSTORE_PASS      Secret text
UMP_ANDROID_KEY_ALIAS          Secret text
UMP_ANDROID_KEY_ALIAS_PASS     Secret text
```

If `UMP_ANDROID_KEYSTORE` is not configured, the release branch falls back to the project/machine keystore resolver described below.

`release/android-test` does not bind these credentials at all and explicitly disables Unity custom keystore signing.

### Google Drive OAuth 2.0

Drive upload runs after successful Android and iOS builds.

Android keeps the artifact behavior:

```text
<UMP_DRIVE_FOLDER_ID>/<Game name>/<AAB|APK>/<artifact>
```

When `<GameName>_BUILD_INFO.txt` exists, Android also uploads a versioned companion BUILD_INFO into the same AAB/APK folder. Rebuilding the same version updates the same Drive file/revision.

iOS intentionally uploads **no `.app` and no `.ipa` to Drive**. Both `release/ios-test` and `release/ios` upload only:

```text
<UMP_DRIVE_FOLDER_ID>/<Game name>/IOS/<GameName>_BUILD_INFO.txt
```

The iOS BUILD_INFO name is stable (no version suffix). A later iOS build updates the same Drive file so the file ID/share link stays stable.

The uploader preserves the existing behavior:

- Missing game/artifact folders are created automatically.
- If a file with the same name already exists in the destination folder, the uploader updates that file instead of creating another file. The Drive file ID/share link is retained.
- Older duplicate files with the same name are moved to Trash by default.
- Set `UMP_DRIVE_KEEP_DUPLICATES=1` to keep old duplicates.
- Set `UMP_DRIVE_SUBPATH` to override the generated subpath.
- Set `UMP_DRIVE_SUBPATH` to an explicitly empty value to upload directly into the configured root folder.

Drive upload failure is logged but does not fail an otherwise successful game build.

### Create the OAuth client

In Google Cloud:

1. Enable **Google Drive API**.
2. Configure the OAuth consent screen.
3. Create an **OAuth 2.0 Client ID** with application type **Web application**.
4. Add this exact Authorized redirect URI:

```text
https://developers.google.com/oauthplayground
```

### Obtain `UMP_DRIVE_OAUTH_REFRESH_TOKEN`

Open Google OAuth 2.0 Playground and configure:

```text
Use your own OAuth credentials: ON
OAuth flow: Server-side
Access type: Offline
```

Enter the Client ID and Client Secret created above.

Authorize this scope:

```text
https://www.googleapis.com/auth/drive
```

Then choose **Exchange authorization code for tokens** and copy the returned `refresh_token` into the Jenkins Secret Text credential:

```text
UMP_DRIVE_OAUTH_REFRESH_TOKEN
```

The Jenkins uploader exchanges this long-lived refresh token for a short-lived access token on each upload, so no interactive Google login is required during builds.

If Google reports:

```text
Error 400: redirect_uri_mismatch
```

verify that the OAuth client is a **Web application** and its Authorized redirect URI is exactly:

```text
https://developers.google.com/oauthplayground
```

For a long-running Jenkins setup, avoid leaving an External OAuth consent configuration in Testing mode when its refresh-token lifetime is unsuitable for your workflow.

## Build workspace

The pipeline builds outside the hidden Jenkins workspace so the exact project tree can be opened directly in Finder, Unity, or Xcode while debugging.

Typical path:

```text
~/Desktop/PearzBuilds/MeowPuzzle/release_android
```

`Builds/` and generated Xcode projects stay inside that workspace.

The branch/job name is sanitized because Unity 6 can fail on build paths containing Jenkins `%2F` branch encoding.

Override the workspace root with a Jenkins global environment variable:

```text
UMP_WORKSPACE_ROOT=/Users/<you>/Desktop/PearzBuilds
```

## Unity path resolution

No Unity executable path is required in the project.

`Jenkins/find_unity.sh` resolves the Unity version from:

```text
ProjectSettings/ProjectVersion.txt
```

and then locates that editor in Unity Hub installations.

Use the Jenkins environment variable `UNITY_PATH` only when you need an explicit override.

## iOS device build (`release/ios-test`)

The device branch exports into:

```text
Builds/iOS/<sanitized product name>
```

When an existing compatible Xcode project is present, Unity uses:

```text
BuildOptions.AcceptExternalModificationsToPlayer
```

so the export is appended instead of replacing the Xcode project. This preserves Xcode signing/team setup between builds.

Set:

```text
UMP_IOS_CLEAN=1
```

to force a clean Xcode export.

### CocoaPods / Firebase / AppLovin native dependencies

If Unity generates `Builds/iOS/<Game>/Podfile`, `Jenkins/build_ios.sh` runs `pod install` immediately after Unity export. For `release/ios-test`, capability cleanup then runs on that final Pods-integrated project. Device build/archive uses the generated `.xcworkspace` instead of the raw `.xcodeproj`, so native Pods such as Firebase and AppLovin MAX are visible to Xcode.

UMP searches for `pod` in PATH, `/opt/homebrew/bin/pod`, and `/usr/local/bin/pod`. If it is missing and Homebrew exists, UMP installs CocoaPods with:

```bash
brew install cocoapods
```

Useful overrides:

```text
UMP_IOS_POD_BIN=/path/to/pod
UMP_IOS_AUTO_INSTALL_COCOAPODS=0
UMP_IOS_PODS_REPO_UPDATE=1
```

If there is no `Podfile`, UMP keeps the normal `.xcodeproj` build path.

### Firebase test integration (`release/ios-test`)

Jenkins exposes this boolean parameter:

```text
IOS_TEST_ENABLE_FIREBASE_PUSH
```

The parameter name is kept for compatibility, but in UMP 1.0.9 it controls the generated iOS-test Firebase requirements as a group:

- **OFF (default):** remove `com.apple.Push`, remove `aps-environment`, and remove the generated **Crashlytics Run Script** build phase from the exported Xcode project. This avoids Personal Team/APNs signing failures and avoids Crashlytics requiring a missing `GoogleService-Info.plist`. Firebase packages and Unity game source are not edited.
- **ON:** keep APNs + Crashlytics. The signing profile must support Push Notifications and the correct `GoogleService-Info.plist` must be available to the generated Xcode project.

The cleanup runs after Unity export and after `pod install`, so Xcode builds the final `.xcworkspace` after the CI-only edits are applied. Production `release/ios` is not modified by this test-only cleanup.

### Personal Team / In-App Purchase cleanup

For `release/ios-test`, UMP performs device-test-only cleanup after Unity export:

1. `JenkinsBuild.cs` removes `StoreKit.framework` from the `Unity-iPhone` app target.
2. `StoreKit.framework` remains on `UnityFramework`, where Unity IAP/plugin code can still live.
3. `Jenkins/strip_ios_iap.sh` removes a remaining literal `com.apple.InAppPurchase` Xcode capability marker if present.
4. The script verifies that the bundle identifier and signing settings were not changed by the cleanup.
5. The script verifies that StoreKit is no longer linked by more than one target.

The normal `release/ios` Archive/TestFlight flow does not use this device-test cleanup.

Useful overrides:

```text
UMP_IOS_STRIP_IAP=0      # disable Unity-side StoreKit app-target cleanup
UMP_IOS_STRIP_IAP=1      # force it on
UMP_IOS_CLEAN=1          # force clean Unity Xcode export
UMP_IOS_TEAM_ID=<TEAM>   # explicit development team when needed
```

## iOS production (`release/ios`)

The production iOS branch performs the normal archive/export/TestFlight flow. Test-device IAP stripping is intentionally restricted to `release/ios-test` so production capabilities are not modified by that workaround.

## Telegram notifications

Every build posts its result to Telegram. When an artifact is small enough for Telegram upload, it can also be attached; Android notifications include the Drive URL written by the Drive uploader.

Typical message:

```text
✅ MeowPuzzle - SUCCESS
Branch: release/android
Build: #14
Version: 1.0.0 (7)
Package: com.pearz.meowpuzzle
Artifact: MeowPuzzle-v1.0.0.aab
Drive: https://drive.google.com/file/d/.../view
Build Info: https://drive.google.com/file/d/.../view
Jenkins: http://.../job/MeowPuzzle/job/release%2Fandroid/14/
```

`Version`, build number, and `Package` are generated from Unity Player Settings and written to `Builds/ump_build_info.txt`. `Package` is the Android application ID or iOS bundle identifier.

Drive URL metadata is separated so Telegram can show both links without one overwriting the other:

```text
Builds/ump_drive_url.txt                 # APK/AAB artifact URL
Builds/ump_build_info_drive_url.txt      # BUILD_INFO URL
```

For iOS, only the stable `<GameName>_BUILD_INFO.txt` is uploaded to Drive, so Telegram normally shows `Build Info:` and no Drive artifact URL.

The game name normally comes from `PlayerSettings.productName`. Override it with:

```text
UMP_GAME_NAME
```

To use Telegram forum topics, give the bot permission to manage topics. UMP stores automatically-created topic IDs on the Jenkins machine under:

```text
~/.pearz/telegram-topics
```

Optional Jenkins global environment overrides:

```text
UMP_TELEGRAM_AUTO_TOPIC=0
UMP_TELEGRAM_TOPIC_ID=2
UMP_TELEGRAM_TOPICS=MeowPuzzle=2;Sand Shooter=7
```

Telegram notification errors are reported in the log but do not fail the game build.

## Upgrade checklist

When upgrading UMP:

```text
1. Update the Git package tag/revision in Packages/manifest.json.
2. Let Unity resolve the package.
3. Run Pearz > SetupJenkin > Sync if needed.
4. Confirm generated files print the new UMP version.
5. Commit Packages/manifest.json and Packages/packages-lock.json.
6. Commit Jenkinsfile, Assets/Editor/JenkinsBuild.cs and changed Jenkins/* generated files.
7. Push the target release branch.
8. Run Jenkins and verify the expected branch-specific stages in the log.
```

## Current version

```text
UMP 1.0.9
```

Key changes in 1.0.9:

```text
- iOS test: when Firebase is OFF, strip the generated Crashlytics Run Script in addition to APNs requirements.
- Build metadata: add PACKAGE_NAME (Android application ID / iOS bundle identifier).
- Drive: write BUILD_INFO URL separately to Builds/ump_build_info_drive_url.txt.
- Telegram: add Package and Build Info link to the notification.
- Jenkins: clear per-build URL/build-info metadata first to prevent stale links in notifications.
```
