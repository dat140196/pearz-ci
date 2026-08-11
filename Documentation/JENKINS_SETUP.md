# UMP Jenkins Setup

1. Unity Package Manager -> Add package from Git URL.
2. Run `Tools > UMP > Setup / Sync Jenkins Files`.
3. Set Unity executable path and iOS scheme.
4. Check Unity `File > Build Settings` and enable all scenes.
5. Commit generated files.
6. Jenkins -> New Item -> Multibranch Pipeline.
7. Add the Git repository and Git credentials.
8. Build Configuration: `by Jenkinsfile`, Script Path: `Jenkinsfile`.
9. Optional branch filter: `release/(android|ios-test|ios)`.
10. Configure Git webhook for automatic builds.

Branches:
- `release/android` -> Android AAB
- `release/ios-test` -> iOS Xcode project for device testing
- `release/ios` -> iOS archive/export + TestFlight upload

For `release/ios`, configure Apple Developer signing on the Jenkins Mac/Xcode first and verify one manual Archive/Export/Upload before enabling CI.

Do not put Apple passwords in Git. For production authentication, use App Store Connect API-key authentication with Apple's supported upload tooling.
