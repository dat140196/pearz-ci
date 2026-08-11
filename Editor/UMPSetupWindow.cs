#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace UMP
{
    public sealed class UMPSetupWindow : EditorWindow
    {
        private string unityPath = "/Applications/Unity/Hub/Editor/6000.0.XXf1/Unity";
        private string iosScheme = "Unity-iPhone";
        private bool overwrite = true;

        [MenuItem("Tools/UMP/Setup / Sync Jenkins Files")]
        public static void Open()
        {
            var window = GetWindow<UMPSetupWindow>("UMP Mobile Pipeline");
            window.minSize = new Vector2(600, 320);
            window.Show();
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("UMP Mobile Pipeline 1.1.1", EditorStyles.boldLabel);
            EditorGUILayout.Space(8);
            EditorGUILayout.HelpBox(
                "Creates Jenkinsfile and Jenkins build/upload/notification scripts in the Unity project root.",
                MessageType.Info);

            unityPath = EditorGUILayout.TextField("Unity executable", unityPath);
            iosScheme = EditorGUILayout.TextField("iOS scheme", iosScheme);
            overwrite = EditorGUILayout.Toggle("Overwrite existing files", overwrite);

            EditorGUILayout.Space(12);

            if (GUILayout.Button("Create / Sync UMP Files", GUILayout.Height(42)))
                UMPSetup.Run(unityPath, iosScheme, overwrite);

            if (GUILayout.Button("Open Jenkins Folder"))
                UMPSetup.OpenJenkinsFolder();
        }
    }
}
#endif
