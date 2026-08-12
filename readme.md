# UMP Unity Mobile Pipeline 1.0.6

Install using Unity Package Manager -> Add package from Git URL.

**Pin the version.** An unpinned git URL makes Unity contact GitHub on
every single build to check whether the branch moved, so a network hiccup
aborts the build with `Project has invalid dependencies`. Add `#<tag>` in
`Packages/manifest.json`:

```json
"com.ump.pearz-build-pipeline": "https://github.com/dat140196/pearz-ci.git#1.0.6"
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

## Build workspace

The job does **not** build in the hidden Jenkins workspace. It checks the
project out on the **Desktop of the build machine**, so the exact tree
Jenkins built can be opened in Finder, Unity or Xcode while a failure is
being looked at:

```
~/Desktop/PearzBuilds/<job name>/<branch>
```

`Builds/` and the generated Xcode project are inside that folder as usual.

`~` is the home of the **user Jenkins runs as**. Started with
`brew services start jenkins-lts` that is your own account and the folder
shows up on your Desktop right away. Installed as the system service, it
is the `jenkins` user instead, whose Desktop no Finder window ever shows -
point the build somewhere visible with a global environment variable
(**Manage Jenkins > System > Global properties > Environment variables**):

```
UMP_WORKSPACE_ROOT = /Users/<you>/Desktop/PearzBuilds
```

That user then needs write access to the folder. The first build after
this change re-clones the project into the new location; the old workspace
under `~/.jenkins/workspace` can be deleted by hand.

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
