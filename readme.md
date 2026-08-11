# UMP - Unity Mobile Pipeline

Install this package from Unity Package Manager using a Git URL.

After importing, run:

**Tools > UMP > Setup / Sync Jenkins Files**

It creates the Jenkins files in the Unity project root:

- Jenkinsfile
- Assets/Editor/JenkinsBuild.cs
- Jenkins/build_android.sh
- Jenkins/build_ios.sh
- Jenkins/archive_ios.sh
- Jenkins/upload_testflight.sh
- Jenkins/ExportOptions.plist
- .gitignore UMP section

Branches:

- `release/android` -> Android AAB
- `release/ios-test` -> iOS Xcode project for device testing
- `release/ios` -> iOS archive/export + TestFlight upload

UMP reads all enabled scenes from Unity Build Settings.

For TestFlight, configure Apple Developer signing on the Jenkins Mac/Xcode first. Do not store Apple passwords in Git.
