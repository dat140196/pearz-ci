#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace UMP
{
    public sealed class UMPSetupWindow : EditorWindow
    {
        private UMPKeystore.Values _values;
        private bool _showPasswords;

        [MenuItem("Pearz/SetupJenkin")]
        public static void Open()
        {
            var window = GetWindow<UMPSetupWindow>("Pearz Setup Jenkins");
            window.minSize = new Vector2(520, 380);
            window.Show();
        }

        // Start from what the project already has, so a sync done to
        // pick up new templates does not wipe the signing values.
        private void OnEnable()
        {
            _values = UMPKeystore.Read(UMPKeystore.PropertiesPath());
        }

        private void OnGUI()
        {
            string packageRoot = UMPSetup.FindPackageRoot();

            EditorGUILayout.LabelField(
                "UMP Mobile Pipeline " + UMPSetup.PackageVersion(packageRoot),
                EditorStyles.boldLabel);

            EditorGUILayout.Space(8);

            EditorGUILayout.HelpBox(
                "The Jenkinsfile and the Jenkins build/upload/notification " +
                "scripts are written into this project automatically when the " +
                "package is installed or updated.\n\n" +
                "Sync below forces that generation and writes the Android " +
                "signing values into Keystores/<package-name>.properties.",
                MessageType.Info);

            EditorGUILayout.Space(12);

            DrawKeystore();

            EditorGUILayout.Space(12);

            if (GUILayout.Button("Sync", GUILayout.Height(48)))
                Sync();

            EditorGUILayout.Space(4);

            EditorGUILayout.BeginHorizontal();

            if (GUILayout.Button("Open Jenkins Folder"))
                UMPSetup.OpenJenkinsFolder();

            if (GUILayout.Button("Open Keystores Folder"))
                UMPSetup.OpenKeystoresFolder();

            EditorGUILayout.EndHorizontal();
        }

        private void DrawKeystore()
        {
            EditorGUILayout.LabelField("Android signing", EditorStyles.boldLabel);

            string package = UMPKeystore.PackageName();

            if (string.IsNullOrEmpty(package))
            {
                EditorGUILayout.HelpBox(
                    "Player Settings has no Android package name yet, so the " +
                    ".properties file cannot be named. Set it in " +
                    "Player Settings > Other Settings > Package Name.",
                    MessageType.Warning);
            }
            else
            {
                EditorGUILayout.LabelField(
                    "File",
                    UMPKeystore.FolderName + "/" + package + ".properties");
            }

            EditorGUILayout.Space(4);

            _values.StorePass = Field("storePass", _values.StorePass);
            _values.Alias = Field("alias", _values.Alias);
            _values.AliasPass = Field("aliasPass", _values.AliasPass);

            _showPasswords = EditorGUILayout.ToggleLeft(
                "Show passwords", _showPasswords);

            EditorGUILayout.Space(4);

            if (_values.IsEmpty)
            {
                EditorGUILayout.HelpBox(
                    "Empty: Sync writes no .properties file.",
                    MessageType.None);
            }
            else if (string.IsNullOrEmpty(_values.StorePass) ||
                     string.IsNullOrEmpty(_values.Alias))
            {
                EditorGUILayout.HelpBox(
                    "storePass and alias are both required for the build to " +
                    "sign. aliasPass may stay empty when the alias uses the " +
                    "store password.",
                    MessageType.Warning);
            }
            else if (!string.IsNullOrEmpty(package) &&
                     UMPKeystore.KeystoreFile() == null)
            {
                EditorGUILayout.HelpBox(
                    "No " + package + ".keystore (or .jks) in " +
                    UMPKeystore.FolderName + "/ yet. The key file itself is " +
                    "never generated - create it with keytool and commit it " +
                    "next to the .properties file.",
                    MessageType.Warning);
            }
        }

        private string Field(string label, string value)
        {
            bool secret =
                !_showPasswords &&
                label.IndexOf("Pass", System.StringComparison.Ordinal) >= 0;

            // The IMGUI fields throw on a null string.
            string text = value ?? string.Empty;

            return secret
                ? EditorGUILayout.PasswordField(label, text)
                : EditorGUILayout.TextField(label, text);
        }

        // One button: regenerate the pipeline files, then write the
        // signing values, and report both in a single dialog.
        private void Sync()
        {
            if (!UMPSetup.Sync(false))
                return;

            string keystore = UMPKeystore.Sync(_values);

            // Read back what landed on disk, so the window shows the
            // file rather than the values that were typed into it.
            _values = UMPKeystore.Read(UMPKeystore.PropertiesPath());

            GUI.FocusControl(null);

            EditorUtility.DisplayDialog(
                "UMP",
                "UMP files synced successfully.\n\n" +
                "release/android -> AAB\n" +
                "release/android-test -> APK\n" +
                "release/ios-test -> iOS device build\n" +
                "release/ios -> TestFlight\n\n" +
                "Artifacts are named ProductName-vVersion.\n" +
                "Unity is auto-detected on the build machine.\n\n" +
                keystore,
                "OK");
        }
    }
}
#endif
