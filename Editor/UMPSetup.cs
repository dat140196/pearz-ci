#if UNITY_EDITOR
using System;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace UMP.Editor
{
    public static class UMPSetup
    {
        public static void Run(string unityPath, string iosScheme, bool overwrite)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string packageRoot = FindPackageRoot();

            if (string.IsNullOrEmpty(packageRoot))
            {
                EditorUtility.DisplayDialog("UMP", "Cannot locate UMP package root.", "OK");
                return;
            }

            Copy(projectRoot, packageRoot, "Templates/Jenkinsfile.template", "Jenkinsfile", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/JenkinsBuild.cs.template", "Assets/Editor/JenkinsBuild.cs", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/build_android.sh.template", "Jenkins/build_android.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/build_ios.sh.template", "Jenkins/build_ios.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/archive_ios.sh.template", "Jenkins/archive_ios.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/upload_testflight.sh.template", "Jenkins/upload_testflight.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/upload_drive.sh.template", "Jenkins/upload_drive.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/upload_drive_impl.py", "Jenkins/upload_drive_impl.py", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/notify_telegram.sh.template", "Jenkins/notify_telegram.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/ExportOptions.plist.template", "Jenkins/ExportOptions.plist", overwrite, unityPath, iosScheme);

            AppendGitignore(projectRoot, packageRoot);

            MakeExecutable(Path.Combine(projectRoot, "Jenkins/build_android.sh"));
            MakeExecutable(Path.Combine(projectRoot, "Jenkins/build_ios.sh"));
            MakeExecutable(Path.Combine(projectRoot, "Jenkins/archive_ios.sh"));
            MakeExecutable(Path.Combine(projectRoot, "Jenkins/upload_testflight.sh"));

            AssetDatabase.Refresh();

            EditorUtility.DisplayDialog(
                "UMP",
                "UMP files created/synced.\n\n" +
                "Next: check Build Settings scenes, review Jenkinsfile, configure Xcode signing, then commit/push.",
                "OK");
        }

        public static void OpenJenkinsFolder()
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string path = Path.Combine(projectRoot, "Jenkins");
            Directory.CreateDirectory(path);
            EditorUtility.RevealInFinder(path);
        }

        private static string FindPackageRoot()
        {
            string[] guids = AssetDatabase.FindAssets("UMPSetup t:Script");
            foreach (string guid in guids)
            {
                string asset = AssetDatabase.GUIDToAssetPath(guid).Replace("\", "/");
                if (asset.EndsWith("Editor/UMPSetup.cs"))
                {
                    string full = Path.GetFullPath(Path.Combine(
                        Directory.GetParent(Application.dataPath).FullName, asset));
                    return Directory.GetParent(Directory.GetParent(full).FullName).FullName;
                }
            }
            return null;
        }

        private static void Copy(string projectRoot, string packageRoot, string sourceRel, string destRel,
            bool overwrite, string unityPath, string iosScheme)
        {
            string source = Path.Combine(packageRoot, sourceRel);
            string dest = Path.Combine(projectRoot, destRel);

            if (!File.Exists(source))
                throw new FileNotFoundException("UMP template missing: " + source);

            if (!overwrite && File.Exists(dest))
                return;

            Directory.CreateDirectory(Path.GetDirectoryName(dest));

            string text = File.ReadAllText(source)
                .Replace("__UMP_UNITY_PATH__", unityPath ?? "")
                .Replace("__UMP_IOS_SCHEME__", iosScheme ?? "Unity-iPhone");

            File.WriteAllText(dest, text);
        }

        private static void AppendGitignore(string projectRoot, string packageRoot)
        {
            string dest = Path.Combine(projectRoot, ".gitignore");
            string marker = "# UMP Mobile Pipeline";

            if (File.Exists(dest) && File.ReadAllText(dest).Contains(marker))
                return;

            string template = File.ReadAllText(
                Path.Combine(packageRoot, "Templates/UMP.gitignore.template"));

            File.AppendAllText(dest, Environment.NewLine + Environment.NewLine + template);
        }

        private static void MakeExecutable(string path)
        {
            if (!File.Exists(path)) return;

            try
            {
                var p = new Process();
                p.StartInfo.FileName = "/bin/chmod";
                p.StartInfo.Arguments = "+x "" + path + """;
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.Start();
                p.WaitForExit();
            }
            catch { }
        }
    }
}
#endif
