#if UNITY_EDITOR
using System;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace UMP
{
    public static class UMPSetup
    {
        public static void Run(string unityPath, string iosScheme, bool overwrite)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string packageRoot = FindPackageRoot();

            if (string.IsNullOrEmpty(packageRoot))
            {
                EditorUtility.DisplayDialog(
                    "UMP",
                    "Cannot locate the installed UMP package root.",
                    "OK");
                return;
            }

            Copy(projectRoot, packageRoot, "Templates/Jenkinsfile.template",
                "Jenkinsfile", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/JenkinsBuild.cs.template",
                "Assets/Editor/JenkinsBuild.cs", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/build_android.sh.template",
                "Jenkins/build_android.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/build_ios.sh.template",
                "Jenkins/build_ios.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/archive_ios.sh.template",
                "Jenkins/archive_ios.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/upload_testflight.sh.template",
                "Jenkins/upload_testflight.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/upload_drive.sh.template",
                "Jenkins/upload_drive.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/upload_drive_impl.py",
                "Jenkins/upload_drive_impl.py", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/notify_telegram.sh.template",
                "Jenkins/notify_telegram.sh", overwrite, unityPath, iosScheme);
            Copy(projectRoot, packageRoot, "Templates/ExportOptions.plist.template",
                "Jenkins/ExportOptions.plist", overwrite, unityPath, iosScheme);

            AppendGitignore(projectRoot, packageRoot);

            MakeExecutable(projectRoot, "Jenkins/build_android.sh");
            MakeExecutable(projectRoot, "Jenkins/build_ios.sh");
            MakeExecutable(projectRoot, "Jenkins/archive_ios.sh");
            MakeExecutable(projectRoot, "Jenkins/upload_testflight.sh");
            MakeExecutable(projectRoot, "Jenkins/upload_drive.sh");
            MakeExecutable(projectRoot, "Jenkins/upload_drive_impl.py");
            MakeExecutable(projectRoot, "Jenkins/notify_telegram.sh");

            AssetDatabase.Refresh();

            EditorUtility.DisplayDialog(
                "UMP",
                "UMP files created/synced successfully.\n\n" +
                "release/android -> AAB\n" +
                "release/android-test -> APK\n" +
                "release/ios-test -> iOS device build\n" +
                "release/ios -> TestFlight\n\n" +
                "Drive + Telegram files were installed.",
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
                string assetPath = AssetDatabase.GUIDToAssetPath(guid).Replace("\\", "/");

                if (!assetPath.EndsWith("Editor/UMPSetup.cs", StringComparison.Ordinal))
                    continue;

                string projectRoot = Directory.GetParent(Application.dataPath).FullName;
                string fullPath = Path.GetFullPath(Path.Combine(projectRoot, assetPath));

                DirectoryInfo editorDir = Directory.GetParent(fullPath);
                DirectoryInfo packageDir = editorDir != null ? editorDir.Parent : null;

                return packageDir != null ? packageDir.FullName : null;
            }

            return null;
        }

        private static void Copy(
            string projectRoot,
            string packageRoot,
            string sourceRelative,
            string destinationRelative,
            bool overwrite,
            string unityPath,
            string iosScheme)
        {
            string source = Path.Combine(packageRoot, sourceRelative);
            string destination = Path.Combine(projectRoot, destinationRelative);

            if (!File.Exists(source))
                throw new FileNotFoundException("UMP template missing: " + source);

            if (!overwrite && File.Exists(destination))
                return;

            string directory = Path.GetDirectoryName(destination);
            if (!string.IsNullOrEmpty(directory))
                Directory.CreateDirectory(directory);

            string content = File.ReadAllText(source)
                .Replace("__UMP_UNITY_PATH__", unityPath ?? "")
                .Replace("__UMP_IOS_SCHEME__", iosScheme ?? "Unity-iPhone");

            File.WriteAllText(destination, content);
        }

        private static void AppendGitignore(string projectRoot, string packageRoot)
        {
            string destination = Path.Combine(projectRoot, ".gitignore");
            string marker = "# UMP Mobile Pipeline";

            if (File.Exists(destination) &&
                File.ReadAllText(destination).Contains(marker))
                return;

            string template = File.ReadAllText(
                Path.Combine(packageRoot, "Templates/UMP.gitignore.template"));

            File.AppendAllText(
                destination,
                Environment.NewLine + Environment.NewLine + template);
        }

        private static void MakeExecutable(string projectRoot, string relativePath)
        {
            string path = Path.Combine(projectRoot, relativePath);
            if (!File.Exists(path))
                return;

            try
            {
                using (var process = new Process())
                {
                    process.StartInfo.FileName = "/bin/chmod";
                    process.StartInfo.Arguments = "+x \"" + path + "\"";
                    process.StartInfo.UseShellExecute = false;
                    process.StartInfo.CreateNoWindow = true;
                    process.Start();
                    process.WaitForExit();
                }
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogWarning(
                    "[UMP] chmod failed for " + path + ": " + ex.Message);
            }
        }
    }
}
#endif
