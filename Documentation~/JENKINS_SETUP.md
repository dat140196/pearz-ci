# UMP Jenkins Setup 1.12.0

## Install / sync

Install the package from its Git URL. The Jenkinsfile, `Jenkins/*` scripts,
`Assets/Editor/JenkinsBuild.cs` and the `.gitignore` block are written
automatically the first time the editor loads the package, and again after
every package update. The signature (package version + template contents) is
cached in `Library/UMP.sync`; auto sync is skipped in batch mode so Jenkins
builds never rewrite their own workspace.

Force a sync from **Pearz > SetupJenkin** -> `Force Sync UMP Files`.
Commit the generated files.

Branches:
- release/android -> AAB
- release/android-test -> APK
- release/ios-test -> build and install on the device attached to the Mac
- release/ios -> Archive/Export + TestFlight

Create a Multibranch Pipeline, connect the Git repository, use Jenkinsfile at project root, and optionally filter `release/(android|android-test|ios-test|ios)`.

## Build on push (no Build Now)

The Jenkinsfile declares `triggers { pollSCM('H/2 * * * *') }`, so once a
branch has been built one time, Jenkins picks up new commits by itself
within ~2 minutes. Nothing else is required - but a webhook makes it
instant, and branch discovery still needs one of the two settings below.

**1. Branch discovery (required when there is no webhook)**

Polling only watches branches Jenkins already knows, so a brand-new branch
is never noticed. In the Multibranch job -> Configure -> *Scan Multibranch
Pipeline Triggers* -> tick **Periodically if not otherwise run** and set
`1 minute`.

With a working webhook on the GitHub branch source this is not needed -
the push event indexes the new branch by itself. Keep it at `1 day` as a
safety net.

**2. Webhook (makes it instant)**

The webhook alone is not enough: the Jenkins side must be able to receive
it. There is no *GitHub hook trigger for GITScm polling* checkbox in a
Multibranch job - that option only exists on freestyle/single pipeline
jobs. A Multibranch job reacts to a push event only through its
**Branch Source**.

GitHub, payload URL `http://<jenkins>/github-webhook/`, content type
`application/json`, event *Just the push event*:

1. Manage Jenkins -> System -> **Jenkins URL** = the URL GitHub can reach.
   It is also the link Telegram sends.
2. Job -> Configure -> **Branch Sources** must be **GitHub**, not the plain
   **Git** source. `/github-webhook/` is ignored by the plain Git source.
   Use an HTTPS repo URL plus a personal access token credential.
3. Behaviours: *Discover branches*. Optional *Filter by name (with regular
   expression)*: `release/(android|android-test|ios-test|ios)`.
4. Save, then **Scan Repository Now** once. Branch jobs only exist after
   the first scan, and a Jenkinsfile trigger is only registered after the
   branch has been built once.
5. Push, then check GitHub -> Settings -> Webhooks -> *Recent Deliveries*.
   `200`/`302` means Jenkins received it. A timeout or connection error
   means github.com cannot reach the Mac (LAN only / no port forwarding) -
   expose it through a tunnel or keep relying on `pollSCM`.

Already stuck with the plain **Git** branch source? Two options that work
without switching:

- Git plugin endpoint: `http://<jenkins>/git/notifyCommit?url=<repo-url>`
  (the URL must match the one configured in the job, character for
  character).
- Install *Multibranch Scan Webhook Trigger*, set a token in the job, and
  call `http://<jenkins>/multibranch-webhook-trigger/invoke?token=<token>`.

Other hosts: GitLab -> `http://<jenkins>/project/<job-name>`,
Bitbucket -> `http://<jenkins>/bitbucket-hook/`.

Once deliveries return 200 you can drop the `triggers { pollSCM(...) }`
block from the Jenkinsfile; keeping it costs one `git ls-remote` every two
minutes and covers you when a delivery is lost.

**Behaviour**

- Push to `release/android-test` -> APK build starts on its own.
- Push to any other branch (`main`, feature branches) -> the build ends
  immediately as `NOT_BUILT`, with no Telegram message and no artifact.
  Set the branch filter in the job to skip indexing them entirely.
- Two quick pushes never run two Unity instances on the same workspace:
  `disableConcurrentBuilds()` queues the second one. That is per branch -
  if you also want to stop `release/android` and `release/ios` from
  building at the same time on one Mac, set the agent's *number of
  executors* to 1.
- Only the last 15 builds and the artifacts of the last 3 are kept.

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

## Artifact names

Artifacts are named from Player Settings: `ProductName-vBundleVersion`.
`Meow Puzzle` + version `1.0.0` gives:

- `Builds/AndroidTest/MeowPuzzle-v1.0.0.apk`
- `Builds/Android/MeowPuzzle-v1.0.0.aab`
- `Builds/iOSExport/MeowPuzzle-v1.0.0.ipa`

Spaces and characters that are illegal in file names are stripped.

The iOS Xcode project is exported to `Builds/iOS/<Game name>/` (e.g.
`Builds/iOS/MeowPuzzle/Unity-iPhone.xcodeproj`) so two projects never
share a path on the same machine. The scripts locate the `.xcodeproj`
under `Builds/iOS` instead of assuming a fixed path; `UMP_IOS_PROJECT`
overrides it. The archive is named `Builds/iOSArchive/<Game name>.xcarchive`.

`JenkinsBuild` also writes `Builds/ump_build_info.txt`
(`PRODUCT_NAME`, `PRODUCT_NAME_SAFE`, `VERSION`, `BUILD_NUMBER`, `ARTIFACT`),
which the shell scripts read. Bump the version in Player Settings to get a
new file name - nothing in Jenkins has to change.

## Android signing (keystore)

Unity **never creates a release keystore**. If none is configured it signs
with the Android debug key (`~/.android/debug.keystore`, which the Android
SDK does generate on its own):

- `release/android-test` (APK) - debug key is fine, the APK installs on a
  device. Only use a release key if you need a stable SHA-1 for Google
  Sign-In / Play Games / Firebase.
- `release/android` (AAB) - Google Play **rejects** a debug-signed bundle,
  and the upload key can never be changed afterwards. A real keystore is
  required, so the build fails on purpose when it is missing.

Setting the keystore in *Player Settings -> Publishing Settings* is not
enough for CI: Unity does not save the passwords in the project, so a
`-batchmode` build has no way to read them.

`Jenkins/resolve_keystore.sh` resolves the key by **package name**
(`applicationIdentifier`), so **no project needs its own Jenkins
credential**. It searches three places, first hit wins.

### 1. Keystores/ in the project repo (normal way)

Commit the key with the game; a push is all Jenkins needs.

```
Keystores/
  com.pearz.meowpuzzle.keystore
  com.pearz.meowpuzzle.properties
```

`<package>.properties`:

```
storePass=...
alias=pearz
aliasPass=...
```

The folder and a `README.md` are created by the sync. `.jks` works as well
as `.keystore`, and `aliasPass` may be omitted when the alias uses the
store password.

Lookup keys, in this order:

1. Android `applicationIdentifier` from `ProjectSettings.asset`
   (`com.pearz.meowpuzzle`) - maps 1:1 to a Play listing
2. Product name without spaces (`MeowPuzzle`)
3. `default`

A folder per key also works, handy when the `.jks` comes from elsewhere:

```
Keystores/com.pearz.othergame/
  keystore.properties      <- may contain keystore=../other/release.jks
  release.jks
```

**The passwords are plain text in the repo, so keep the repository
private** - anyone who can read it can sign a build as you. To avoid that,
commit only the `.keystore` and leave the `.properties` out: the resolver
then takes `UMP_ANDROID_KEYSTORE_PASS`, `UMP_ANDROID_KEY_ALIAS` and
`UMP_ANDROID_KEY_ALIAS_PASS` from the environment (Jenkins credentials),
which is one set of credentials for all projects that share a password
scheme.

### 2. Keystore store on the build machine

Same naming, for keys that must never be in a repo:

```
~/.pearz/keystores/            <- $UMP_KEYSTORE_HOME
  com.pearz.othergame.keystore
  com.pearz.othergame.properties
  default.keystore             <- fallback for every project
  default.properties
```

```
chmod 700 ~/.pearz/keystores && chmod 600 ~/.pearz/keystores/*
```

### 3. Per-job credentials (highest priority)

If one job must use its own key, bind these credentials in it - they win
over both folders. With one Jenkins **folder** per game the same four IDs
hold different values per folder, so the number of credential *IDs* stays
at four however many projects there are.

| Credential ID | Kind | Value |
| --- | --- | --- |
| `UMP_ANDROID_KEYSTORE` | Secret file | the `.keystore` / `.jks` file |
| `UMP_ANDROID_KEYSTORE_PASS` | Secret text | store password |
| `UMP_ANDROID_KEY_ALIAS` | Secret text | alias name |
| `UMP_ANDROID_KEY_ALIAS_PASS` | Secret text | alias password |

Either way `JenkinsBuild.ConfigureSigning` sets `PlayerSettings.Android.*`
before building, and nothing is printed except the keystore path and the
alias.

Passwords read from a `.properties` file are handed to Unity through a
`chmod 600` temp file that is deleted when the build ends, **not** through
environment variables: when a Gradle task fails, Unity dumps the whole
environment into the build log, and Jenkins only masks values that came
from its own credentials.

If the alias is wrong the Gradle error is explicit:
`No key with alias 'x' found in keystore`. List what is really inside:

```
keytool -list -v -keystore Keystores/<package>.keystore
```

### Creating a keystore

Once per game - keep the file and its passwords backed up, losing them
means losing the ability to update the app on Play:

```
keytool -genkeypair -v -keystore Keystores/com.pearz.meowpuzzle.keystore \
  -alias pearz -keyalg RSA -keysize 2048 -validity 10000
```

Name the file after the package so the resolver finds it, commit it, push.
If the project `.gitignore` ignores `*.keystore`, the UMP block re-includes
`Keystores/` - check with `git check-ignore -v Keystores/<file>`.

If Google Play App Signing is enabled for the app, this key is the *upload*
key; Google re-signs with the app signing key.

## Google Drive

Android only. iOS goes to TestFlight (`release/ios`) or is installed
straight onto the device from the Xcode project (`release/ios-test`), so
the Drive stage is skipped on iOS branches.

Layout inside the root folder:

```
<UMP_DRIVE_FOLDER_ID>/
  Meow Puzzle/
    APK/  MeowPuzzle-v1.0.0.apk
    AAB/  MeowPuzzle-v1.0.0.aab
```

Folders are created on first use and reused afterwards. The game folder
name is the Player Settings product name; override it with
`UMP_DRIVE_GAME_NAME`, or replace the whole sub path with
`UMP_DRIVE_SUBPATH` (set it empty to upload into the root folder).

**Same name = overwrite.** Rebuilding without bumping the version uploads
a new revision of the existing file instead of a second copy, so the Drive
link you already gave to testers keeps working and always points at the
latest build. Duplicates left by earlier builds are moved to the trash;
set `UMP_DRIVE_KEEP_DUPLICATES=1` to leave them alone. Bumping the version
in Player Settings still produces a new file, because the name changes.

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

Create an OAuth client (Desktop app), get a refresh token for scope `https://www.googleapis.com/auth/drive` (the narrower `drive.file` scope cannot see folders it did not create, so the `Game/APK` lookup would fail), then set these Jenkins credentials instead of the service-account JSON:
- `UMP_DRIVE_OAUTH_CLIENT_ID`
- `UMP_DRIVE_OAUTH_CLIENT_SECRET`
- `UMP_DRIVE_OAUTH_REFRESH_TOKEN`

and bind them in the `Drive Upload` stage of the Jenkinsfile the same way the service-account credential is bound.

Uploads use the Drive v3 resumable flow in 8 MB chunks with `supportsAllDrives=true`, so large APK/AAB files stream instead of being buffered whole. A failed Drive upload never fails the Jenkins build.

## iOS

Configure Xcode signing on the Jenkins Mac and verify manual
Archive/Export/Upload before CI. No Apple password is stored in UMP. The
Xcode scheme is read from the generated project; set `IOS_SCHEME` in
Jenkins only to override it.

### release/ios-test - install on the attached device

The branch does three things: Unity generates the Xcode project,
`xcodebuild` compiles it for the attached device, and the `.app` is
installed on it (and launched).

Requirements on the Mac:

- The device is plugged in, **unlocked**, and has trusted this Mac
- Xcode is signed in to an Apple Developer account whose provisioning
  profile includes that device's UDID
- `xcrun devicectl` (Xcode 15+) handles the install; `ios-deploy`
  (`brew install ios-deploy`) is used as a fallback for older setups

### Signing team

The Team ID is a 10-character string like `A1B2C3D4E5`. It is **not a
secret** - it is embedded in every build - so if you set it in Jenkins it
belongs in *Manage Jenkins -> System -> Global properties -> Environment
variables*, **not** in Credentials. A credential would not even reach the
script: the Jenkinsfile never binds it.

Resolution order:

1. `UMP_IOS_TEAM_ID`
2. *Player Settings -> iOS -> Identification -> Signing Team ID*, which
   Unity writes into the Xcode project. Ticking *Automatically Sign* alone
   is **not enough** - an empty team field fails with
   `Signing for "Unity-iPhone" requires a development team`.
3. The signing certificate installed on the Mac. The team is read from the
   `OU` of an *Apple Development* certificate, so in practice nothing has
   to be configured at all. If the Mac holds certificates for several
   teams, the script lists them and stops rather than guessing.

Nothing found at all stops the stage immediately with instructions instead
of handing xcodebuild a project it cannot sign.

**No paid Apple Developer account?** A free Apple ID is enough for
`release/ios-test`: sign in to Xcode once on the Jenkins Mac (Settings ->
Accounts -> +), which creates a *Personal Team* and installs the
certificate that step 3 picks up. Limits: the app stops running after
**7 days**, max 3 apps per device, and no push notifications, IAP or Game
Center. Good enough to hand a build to a tester, not for TestFlight
(`release/ios` needs a paid account).

Optional Jenkins env vars:

| Variable | Meaning |
| --- | --- |
| `UMP_IOS_TEAM_ID` | override the Player Settings team for every project |
| `UMP_IOS_DEVICE_UDID` | pick one device when several are attached |
| `UMP_IOS_DEVICE_NAME` | ... or pick it by name |
| `UMP_IOS_CONFIGURATION` | `Release` (default) or `Debug` |
| `UMP_IOS_LAUNCH=0` | install only, do not start the app |

The device list comes from `xcrun xctrace list devices`; only physical,
online devices are considered. With no device attached the stage fails
with the list of what Xcode can actually see, instead of reporting a
success that installed nothing.
