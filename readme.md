# Pearz Unity Mobile Pipeline

Pearz Unity Mobile Pipeline for Jenkins Android/iOS builds, TestFlight, Google Drive artifact upload, Telegram notifications, Android release signing, iOS device deployment, and SSH Git submodules.

## Install

Install with Unity Package Manager using **Add package from Git URL**:

```text
https://github.com/dat140196/pearz-ci.git#1.0.8
```

Pin the package version/tag in `Packages/manifest.json` so Unity does not have to follow a moving Git revision on every build:

```json
{
  "dependencies": {
    "com.ump.pearz-build-pipeline": "https://github.com/dat140196/pearz-ci.git#1.0.8"
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
| `release/ios-test` | Xcode project + direct device install | Append existing Xcode project, Personal Team/device signing, test-only IAP cleanup |
| `release/ios` | Archive / Export / TestFlight | Production iOS flow; device-test IAP cleanup is not applied |

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

Create these four credentials as **Secret text**:

```text
UMP_DRIVE_OAUTH_CLIENT_ID
UMP_DRIVE_OAUTH_CLIENT_SECRET
UMP_DRIVE_OAUTH_REFRESH_TOKEN
UMP_DRIVE_FOLDER_ID
```

`UMP_DRIVE_SERVICE_ACCOUNT_JSON` is no longer used.

### Telegram

Create these as **Secret text**:

```text
UMP_TELEGRAM_BOT_TOKEN
UMP_TELEGRAM_CHAT_ID
```

### iOS keychain

When required by the Jenkins Mac/Xcode setup:

```text
UMP_KEYCHAIN_PASSWORD
```

## SSH Git submodules

Before Unity starts, Jenkins now initializes SSH submodules on every supported release branch. This is required for Unity local packages stored in submodules, for example:

```text
Packages/com.pearz.thirdparty
```

Example `.gitmodules`:

```ini
[submodule "Packages/com.pearz.thirdparty"]
    path = Packages/com.pearz.thirdparty
    url = git@github.com:PearzGame/pearz-thirdparty.git
```

The pipeline runs approximately:

```bash
git submodule sync --recursive
git submodule foreach --recursive 'git reset --hard || true'
git submodule foreach --recursive 'git clean -fd || true'
git submodule update --init --recursive --force
git submodule status --recursive
```

If `.gitmodules` does not exist, the stage is skipped cleanly.

If `.gitmodules` declares `Packages/com.pearz.thirdparty`, Jenkins additionally verifies:

```text
Packages/com.pearz.thirdparty/package.json
```

This prevents Unity Package Manager from failing later with a misleading local-package dependency error.

## Android signing

### `release/android`

This branch builds the Google Play `.aab` and **must use the release key**.

Keystore lookup order is:

1. Jenkins `UMP_ANDROID_*` credentials when configured.
2. `Keystores/` inside the game repository.
3. `~/.pearz/keystores` on the build machine, or `UMP_KEYSTORE_HOME` when overridden.

A project keystore layout can look like:

```text
Keystores/
  com.pearz.meowpuzzle.keystore
  com.pearz.meowpuzzle.properties
```

Example properties:

```properties
storePass=your-store-password
alias=pearz
aliasPass=your-alias-password
```

Create a key once and back it up safely:

```bash
keytool -genkeypair -v \
  -keystore Keystores/com.pearz.meowpuzzle.keystore \
  -alias pearz \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

Verify the real alias when debugging signing errors:

```bash
keytool -list -v -keystore Keystores/com.pearz.meowpuzzle.keystore
```

### `release/android-test`

This branch builds an APK with Android debug/default signing.

The pipeline intentionally:

```text
- does not request Jenkins release-keystore credentials
- does not run the release keystore resolver
- clears stale UMP_ANDROID_* environment variables
- sets PlayerSettings.Android.useCustomKeystore = false
```

This prevents a test APK from being accidentally signed with the production key.

## Google Drive OAuth 2.0

Android artifacts are uploaded after a successful Android build.

Default Drive path:

```text
<UMP_DRIVE_FOLDER_ID>/<Game name>/<AAB|APK>/<artifact>
```

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
Artifact: MeowPuzzle-v1.0.0.aab
Drive: https://drive.google.com/file/d/.../view
Jenkins: http://.../job/MeowPuzzle/job/release%2Fandroid/14/
```

`Version` is generated from Unity Player Settings and written to `Builds/ump_build_info.txt`.

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
UMP 1.2.7
```

Key changes through 1.2.7:

```text
1.2.3  iOS device build: remove StoreKit.framework from Unity-iPhone only.
1.2.4  Android signing: release keystore only on release/android AAB.
1.2.5  Google Drive: OAuth 2.0 Client ID + refresh token, preserve overwrite/folder logic.
1.2.6  Jenkins: initialize/update SSH Git submodules before Unity Package Manager runs.
1.2.7  Jenkins: use sshUserPrivateKey + GIT_SSH_COMMAND for submodules; no SSH Agent plugin required.
```
