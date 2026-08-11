# UMP Unity Mobile Pipeline 1.1.1

This release fixes the Unity Editor compilation issue in 1.1.0.

Install using Unity Package Manager -> Add package from Git URL.

After import, use:

Tools > UMP > Setup / Sync Jenkins Files

Branches:
- release/android -> AAB
- release/android-test -> APK
- release/ios-test -> iOS Xcode project
- release/ios -> Archive/Export/TestFlight

Jenkins credentials:
- ump-drive-service-account-json (Secret file)
- ump-drive-folder-id (Secret text)
- ump-telegram-bot-token (Secret text)
- ump-telegram-chat-id (Secret text)
