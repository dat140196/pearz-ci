#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace UMP
{
    public sealed class UMPSetupWindow : EditorWindow
    {
        [MenuItem("Tools/UMP/Setup / Sync Jenkins Files")]
        public static void Open()
        {
            var window = GetWindow<UMPSetupWindow>("UMP Mobile Pipeline");
            window.minSize = new Vector2(520, 260);
            window.Show();
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("UMP Mobile Pipeline 1.2.0", EditorStyles.boldLabel);
            EditorGUILayout.Space(8);

            EditorGUILayout.HelpBox(
                "Sync creates the Jenkinsfile and the Jenkins " +
                "build/upload/notification scripts in the Unity project root, " +
                "overwriting the previous versions.\n\n" +
                "No Unity path needed: the build machine resolves Unity from " +
                "ProjectSettings/ProjectVersion.txt, then from Unity Hub.",
                MessageType.Info);

            EditorGUILayout.Space(12);

            if (GUILayout.Button("Sync UMP Files", GUILayout.Height(48)))
                UMPSetup.Run();

            EditorGUILayout.Space(4);

            if (GUILayout.Button("Open Jenkins Folder"))
                UMPSetup.OpenJenkinsFolder();
        }
    }
}
#endif
