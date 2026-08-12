#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace UMP
{
    public sealed class UMPSetupWindow : EditorWindow
    {
        [MenuItem("Pearz/SetupJenkin")]
        public static void Open()
        {
            var window = GetWindow<UMPSetupWindow>("Pearz Setup Jenkins");
            window.minSize = new Vector2(520, 280);
            window.Show();
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("UMP Mobile Pipeline 1.10.0", EditorStyles.boldLabel);
            EditorGUILayout.Space(8);

            EditorGUILayout.HelpBox(
                "The Jenkinsfile and the Jenkins build/upload/notification " +
                "scripts are synced automatically when the package is " +
                "installed or updated.\n\n" +
                "Use the button below only to force a sync, for example after " +
                "editing the generated files by hand.\n\n" +
                "No Unity path needed: the build machine resolves Unity from " +
                "ProjectSettings/ProjectVersion.txt, then from Unity Hub.",
                MessageType.Info);

            EditorGUILayout.Space(12);

            if (GUILayout.Button("Force Sync UMP Files", GUILayout.Height(48)))
                UMPSetup.Run();

            EditorGUILayout.Space(4);

            if (GUILayout.Button("Open Jenkins Folder"))
                UMPSetup.OpenJenkinsFolder();
        }
    }
}
#endif
