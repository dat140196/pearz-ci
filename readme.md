# UMP Unity Mobile Pipeline 1.0.7

Install using Unity Package Manager -> Add package from Git URL.

**Pin the version.** An unpinned git URL makes Unity contact GitHub on
every single build to check whether the branch moved, so a network hiccup
aborts the build with `Project has invalid dependencies`. Add `#<tag>` in
`Packages/manifest.json`:

```json
"com.ump.pearz-build-pipeline": "https://github.com/dat140196/pearz-ci.git#1.0.7"
```

Unity then locks that revision in `packages-lock.json` and reuses its
cache. Change the tag when you want the update.

The Jenkinsfile and the `Jenkins/` scripts are written into the project
**automatically** when the package is installed or updated - nothing to click.

To force a sync (e.g. after editing the generated files by hand):

**Pearz > SetupJenkin** -> `Sync`

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

## Telegram notifications

Every build posts its result to a group, with the artifact attached when
it is 50 MB or smaller:

```
✅ MeowPuzzle - SUCCESS
Branch: release/android
Build: #14
Version: 1.0.0 (7)
Artifact: MeowPuzzle-v1.0.0.aab
Drive: https://drive.google.com/file/d/1sztK.../view
Jenkins: http://.../job/MeowPuzzle/job/release%2Fandroid/14/
```

`Version` is `bundleVersion (versionCode)` from Player Settings - the
Android bundle version code, or the iOS build number on an iOS branch -
read from `Builds/ump_build_info.txt` which Unity writes at the end of the
build. The `Drive` line appears on the Android branches, from
`Builds/ump_drive_url.txt` which the uploader writes; a link left by an
earlier build is ignored unless it belongs to this build's artifact.

The name is the **productName** from Player Settings, so several games on
one Jenkins are told apart at a glance. `UMP_GAME_NAME` overrides it.

**1. Create the bot.** Chat with [@BotFather](https://t.me/BotFather),
`/newbot`, answer the two questions, copy the token
(`8123456789:AAH...`).

**2. Put the bot in the group.** Add it as a member. Then send any message
in the group - a bot cannot see a group it has never received anything
from.

**3. Read the chat id:**

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | grep -o '"chat":{"id":[-0-9]*'
```

A supergroup id looks like `-1001234567890` and the minus sign is part of
it. If nothing comes back, promote the bot to admin (privacy mode hides
normal messages from it) and post again.

**4. Add the two credentials** in Jenkins (*Manage Jenkins > Credentials*),
kind **Secret text**, ID exactly `UMP_TELEGRAM_BOT_TOKEN` and
`UMP_TELEGRAM_CHAT_ID` - the Jenkinsfile looks them up by that ID.

**5. One topic per game.** Turn **Topics** on for the group
(*Group Settings > Topics*) and give the bot the **Manage topics** right
(*Group Settings > Administrators > the bot*). The first build of a game
then creates a topic named after it, and every later build posts inside
that topic.

The Bot API cannot list the topics of a group, so the ids of the topics it
created are remembered on the build machine, in
`~/.pearz/telegram-topics`:

```
-1001234567890	MeowPuzzle	2
-1001234567890	Sand Shooter	7
```

- Delete a line to have the topic created again (renaming a game does the
  same by itself - the old topic is left alone and a new one appears).
- A topic someone **closed** is reopened, a topic someone **deleted** is
  recreated, both on the next build.
- Whatever goes wrong - not a forum, missing rights, bad token - the
  message still lands in the group unthreaded. Telegram never fails a
  build; it only prints a line in the log.

Overrides, as global environment variables in
*Manage Jenkins > System > Global properties*:

```
UMP_TELEGRAM_AUTO_TOPIC = 0                        # never create topics
UMP_TELEGRAM_TOPIC_ID   = 2                        # everything in one topic
UMP_TELEGRAM_TOPICS     = MeowPuzzle=2;Sand Shooter=7   # topics made by hand
```

`UMP_TELEGRAM_TOPICS` wins over what the bot created, which is how an
existing topic is adopted: read its id from the Telegram Web URL
(`t.me/c/<group>/<topic id>/<message id>` - the middle number).

## Build workspace

The job does **not** build in the hidden Jenkins workspace. It checks the
project out on the **Desktop of the build machine**, so the exact tree
Jenkins built can be opened in Finder, Unity or Xcode while a failure is
being looked at:

```
~/Desktop/PearzBuilds/MeowPuzzle/release_android
```

`Builds/` and the generated Xcode project are inside that folder as usual.

The folder is the job name with every unsafe character replaced. The `%2F`
Jenkins puts in `JOB_NAME` for a branch **must** go: Unity 6 dies halfway
through an Android build on a path containing `%`, with
`llvm-objcopy: error: '<path>': No such file or directory` for a file whose
folder is right there.

`~` is the home of the **user Jenkins runs as**, guessed from the parent of
`JENKINS_HOME` because the real `$HOME` is not readable at the point
Jenkins picks the workspace. With the usual `~/.jenkins` that is correct.
When it is not - Jenkins installed as the system service, a `JENKINS_HOME`
somewhere else, a remote agent - set a global environment variable
(**Manage Jenkins > System > Global properties > Environment variables**):

```
UMP_WORKSPACE_ROOT = /Users/<you>/Desktop/PearzBuilds
```

That user then needs write access to the folder. The first build after
this change re-clones the project into the new location; the old workspace
under `~/.jenkins/workspace` can be deleted by hand.

## iOS test install (release/ios-test)

`Jenkins/install_ios_device.sh` compiles the Xcode project Unity exported
and installs it on the device attached to the Jenkins Mac.

A **free Apple ID gives a Personal Team**, and Apple refuses to issue a
development profile with In-App Purchase for one:

```
Cannot create a iOS App Development provisioning profile for "com.x.y".
Personal development teams, including "...", do not support the
In-App Purchase capability.
```

The script therefore strips `com.apple.InAppPurchase` from the **exported**
project (`Builds/`, never the repo or the game code), removes the IAP and
push keys from any `.entitlements` it finds, and - if Xcode still asks for
a capability the team cannot sign - retries once with no entitlements at
all. The test build then has no IAP, no push and no keychain sharing;
`release/ios` (Archive/TestFlight) never goes through this script, so what
ships is untouched.

- `UMP_IOS_STRIP_CAPABILITIES=""` turns all of it off (paid team).
- `UMP_IOS_STRIP_CAPABILITIES="com.apple.InAppPurchase com.apple.Push"`
  strips more when the log names another capability.
- `UMP_IOS_TEAM_ID` picks the team; otherwise Player Settings, then the
  Apple ID signed in to Xcode, then a certificate on the Mac.

Every generated script prints `UMP <version>` at the top. If that version
is older than the package, the branch is running scripts from an earlier
sync - re-sync in Unity and push the `Jenkins/` folder to **that branch**.

## Android signing

No Jenkins credential: the key is committed with the game and looked up by
**package name** (`applicationIdentifier` in Player Settings), in
`Keystores/` next to `Assets/`:

```
Keystores/
  com.pearz.meowpuzzle.keystore
  com.pearz.meowpuzzle.properties
```

Create the key once, then back it up - losing it means the app can never be
updated on Google Play again:

```
keytool -genkeypair -v -keystore Keystores/com.pearz.meowpuzzle.keystore \
  -alias pearz -keyalg RSA -keysize 2048 -validity 10000
```

The `.properties` file is written by **Pearz > SetupJenkin**: fill in
`storePass`, `alias`, `aliasPass` and press `Sync`. The file is named after
the package name and overwritten on every sync; leaving all three fields
empty writes nothing. `aliasPass` may stay empty when the alias uses the
store password, and `alias` must match what is really inside the key file
(`keytool -list -v -keystore Keystores/<package>.keystore`) - a wrong value
fails the build with `No key with alias 'x' found in keystore`.

Lookup order is `<applicationIdentifier>`, the product name without spaces,
then `default`; `Keystores/` in the repo first, then
`~/.pearz/keystores` on the build machine
(`UMP_KEYSTORE_HOME`), then job credentials
(`UMP_ANDROID_KEYSTORE_PASS` / `UMP_ANDROID_KEY_ALIAS` /
`UMP_ANDROID_KEY_ALIAS_PASS`), which win over both.

The passwords are plain text, so the game repository must be **private**.
If the key may not live in git, skip the `.properties` file and use the
Jenkins credentials or the machine store instead.
