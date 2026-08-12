# UMP Jenkins Setup 1.5.0

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
- release/ios-test -> iOS Xcode project for device testing
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
`JenkinsBuild` also writes `Builds/ump_build_info.txt`
(`PRODUCT_NAME`, `PRODUCT_NAME_SAFE`, `VERSION`, `BUILD_NUMBER`, `ARTIFACT`),
which the shell scripts read. Bump the version in Player Settings to get a
new file name - nothing in Jenkins has to change.

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
Configure Xcode signing on the Jenkins Mac and verify manual Archive/Export/Upload before CI. No Apple password is stored in UMP. The Xcode scheme is read from the generated project; set `IOS_SCHEME` in Jenkins only to override it.
