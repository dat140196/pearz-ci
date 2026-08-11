#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace UMP.Editor
{
    public class UMPSetupWindow : EditorWindow
    {
        private string unityPath = "/Applications/Unity/Hub/Editor/6000.0.XXf1/Unity";
        private string iosScheme = "Unity-iPhone";
        private bool overwrite = true;

        [MenuItem("Tools/UMP/Setup / Sync Jenkins Files")]
        public static void Open()
        {
            var w = GetWindow<UMPSetupWindow>("UMP Setup");
            w.minSize = new Vector2(560, 300);
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Unity Mobile Pipeline", EditorStyles.boldLabel);
            EditorGUILayout.Space(8);

            unityPath = EditorGUILayout.TextField("Unity executable", unityPath);
            iosScheme = EditorGUILayout.TextField("iOS Scheme", iosScheme);
            overwrite = EditorGUILayout.Toggle("Overwrite existing files", overwrite);

            EditorGUILayout.Space(12);

            if (GUILayout.Button("Create / Sync UMP Files", GUILayout.Height(40)))
                UMPSetup.Run(unityPath, iosScheme, overwrite);

            if (GUILayout.Button("Open Jenkins Folder"))
                UMPSetup.OpenJenkinsFolder();
        }
    }
}
#endif
