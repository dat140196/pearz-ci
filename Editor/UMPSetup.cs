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
        private static readonly string[,] Files =
        {
            { "Templates~/Jenkinsfile.template", "Jenkinsfile" },
            { "Templates~/JenkinsBuild.cs.template", "Assets/Editor/JenkinsBuild.cs" },
            { "Templates~/find_unity.sh.template", "Jenkins/find_unity.sh" },
            { "Templates~/build_android.sh.template", "Jenkins/build_android.sh" },
            { "Templates~/build_ios.sh.template", "Jenkins/build_ios.sh" },
            { "Templates~/archive_ios.sh.template", "Jenkins/archive_ios.sh" },
            { "Templates~/upload_testflight.sh.template", "Jenkins/upload_testflight.sh" },
            { "Templates~/upload_drive.sh.template", "Jenkins/upload_drive.sh" },
            { "Templates~/upload_drive_impl.py", "Jenkins/upload_drive_impl.py" },
            { "Templates~/notify_telegram.sh.template", "Jenkins/notify_telegram.sh" },
            { "Templates~/ExportOptions.plist.template", "Jenkins/ExportOptions.plist" }
        };

        private static readonly string[] Executables =
        {
            "Jenkins/find_unity.sh",
            "Jenkins/build_android.sh",
            "Jenkins/build_ios.sh",
            "Jenkins/archive_ios.sh",
            "Jenkins/upload_testflight.sh",
            "Jenkins/upload_drive.sh",
            "Jenkins/upload_drive_impl.py",
            "Jenkins/notify_telegram.sh"
        };

        // Sync always overwrites: the package templates are the
        // source of truth. Unity is located by Jenkins/find_unity.sh
        // on the build machine, so nothing has to be configured here.
        public static void Run()
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

            try
            {
                for (int i = 0; i < Files.GetLength(0); i++)
                    Copy(projectRoot, packageRoot, Files[i, 0], Files[i, 1]);
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogError("[UMP] Sync failed: " + ex.Message);

                EditorUtility.DisplayDialog("UMP", "Sync failed:\n\n" + ex.Message, "OK");
                return;
            }

            AppendGitignore(projectRoot, packageRoot);

            foreach (string executable in Executables)
                MakeExecutable(projectRoot, executable);

            AssetDatabase.Refresh();

            EditorUtility.DisplayDialog(
                "UMP",
                "UMP files synced successfully.\n\n" +
                "release/android -> AAB\n" +
                "release/android-test -> APK\n" +
                "release/ios-test -> iOS device build\n" +
                "release/ios -> TestFlight\n\n" +
                "Unity is auto-detected on the build machine\n" +
                "from ProjectSettings/ProjectVersion.txt.",
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
            string destinationRelative)
        {
            string source = Path.Combine(packageRoot, sourceRelative);
            string destination = Path.Combine(projectRoot, destinationRelative);

            if (!File.Exists(source))
                throw new FileNotFoundException("UMP template missing: " + source);

            string directory = Path.GetDirectoryName(destination);
            if (!string.IsNullOrEmpty(directory))
                Directory.CreateDirectory(directory);

            // Shell and Python files run on the Jenkins Mac,
            // so they must keep LF endings.
            string content = File.ReadAllText(source).Replace("\r\n", "\n");

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
                Path.Combine(packageRoot, "Templates~/UMP.gitignore.template"));

            File.AppendAllText(
                destination,
                Environment.NewLine + Environment.NewLine + template);
        }

        private static void MakeExecutable(string projectRoot, string relativePath)
        {
            string path = Path.Combine(projectRoot, relativePath);
            if (!File.Exists(path))
                return;

            if (Application.platform == RuntimePlatform.WindowsEditor)
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
