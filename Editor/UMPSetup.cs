#if UNITY_EDITOR
using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace UMP
{
    public static class UMPSetup
    {
        // source template -> destination inside the Unity project
        internal static readonly string[,] Files =
        {
            { "Templates~/Jenkinsfile.template", "Jenkinsfile" },
            { "Templates~/JenkinsBuild.cs.template", "Assets/Editor/JenkinsBuild.cs" },
            { "Templates~/find_unity.sh.template", "Jenkins/find_unity.sh" },
            { "Templates~/resolve_keystore.sh.template", "Jenkins/resolve_keystore.sh" },
            { "Templates~/build_android.sh.template", "Jenkins/build_android.sh" },
            { "Templates~/build_ios.sh.template", "Jenkins/build_ios.sh" },
            { "Templates~/strip_ios_iap.sh.template", "Jenkins/strip_ios_iap.sh" },
            { "Templates~/install_ios_device.sh.template", "Jenkins/install_ios_device.sh" },
            { "Templates~/archive_ios.sh.template", "Jenkins/archive_ios.sh" },
            { "Templates~/upload_testflight.sh.template", "Jenkins/upload_testflight.sh" },
            { "Templates~/upload_drive.sh.template", "Jenkins/upload_drive.sh" },
            { "Templates~/upload_drive_impl.py", "Jenkins/upload_drive_impl.py" },
            { "Templates~/notify_telegram.sh.template", "Jenkins/notify_telegram.sh" },
            { "Templates~/ExportOptions.plist.template", "Jenkins/ExportOptions.plist" },
            { "Templates~/Keystores.README.template", "Keystores/README.md" }
        };

        private static readonly string[] Executables =
        {
            "Jenkins/find_unity.sh",
            "Jenkins/resolve_keystore.sh",
            "Jenkins/build_android.sh",
            "Jenkins/build_ios.sh",
            "Jenkins/strip_ios_iap.sh",
            "Jenkins/install_ios_device.sh",
            "Jenkins/archive_ios.sh",
            "Jenkins/upload_testflight.sh",
            "Jenkins/upload_drive.sh",
            "Jenkins/upload_drive_impl.py",
            "Jenkins/notify_telegram.sh"
        };

        internal static string ProjectRoot
        {
            get { return Directory.GetParent(Application.dataPath).FullName; }
        }

        // Sync always overwrites: the package templates are the
        // source of truth. Unity is located by Jenkins/find_unity.sh
        // on the build machine, so nothing has to be configured here.
        public static bool Sync(bool silent)
        {
            string projectRoot = ProjectRoot;
            string packageRoot = FindPackageRoot();

            if (string.IsNullOrEmpty(packageRoot))
            {
                Report(silent, "Cannot locate the installed UMP package root.");
                return false;
            }

            string version = PackageVersion(packageRoot);

            try
            {
                for (int i = 0; i < Files.GetLength(0); i++)
                    Copy(projectRoot, packageRoot, Files[i, 0], Files[i, 1], version);
            }
            catch (Exception ex)
            {
                Report(silent, "Sync failed: " + ex.Message);
                return false;
            }

            AppendGitignore(projectRoot, packageRoot);

            foreach (string executable in Executables)
                MakeExecutable(projectRoot, executable);

            AssetDatabase.Refresh();

            UnityEngine.Debug.Log(
                "[UMP] Synced " + Files.GetLength(0) +
                " Jenkins files (v" + PackageVersion(packageRoot) + ").");

            return true;
        }

        public static void OpenJenkinsFolder()
        {
            Reveal(Path.Combine(ProjectRoot, "Jenkins"));
        }

        public static void OpenKeystoresFolder()
        {
            Reveal(UMPKeystore.FolderPath());
        }

        private static void Reveal(string path)
        {
            Directory.CreateDirectory(path);
            EditorUtility.RevealInFinder(path);
        }

        // Any destination missing means the project needs a sync.
        internal static bool FilesMissing()
        {
            string projectRoot = ProjectRoot;

            for (int i = 0; i < Files.GetLength(0); i++)
            {
                if (!File.Exists(Path.Combine(projectRoot, Files[i, 1])))
                    return true;
            }

            return false;
        }

        // Package version + template contents. Changes whenever the
        // installed package changes, which is what triggers auto-sync.
        internal static string Signature(string packageRoot)
        {
            using (var md5 = MD5.Create())
            {
                var buffer = new StringBuilder();

                buffer.Append(PackageVersion(packageRoot));

                for (int i = 0; i < Files.GetLength(0); i++)
                {
                    string source = Path.Combine(packageRoot, Files[i, 0]);

                    if (!File.Exists(source))
                        continue;

                    buffer.Append('|');
                    buffer.Append(Files[i, 0]);
                    buffer.Append(':');
                    buffer.Append(File.ReadAllText(source).Replace("\r\n", "\n"));
                }

                byte[] hash = md5.ComputeHash(
                    Encoding.UTF8.GetBytes(buffer.ToString()));

                var text = new StringBuilder(hash.Length * 2);

                foreach (byte b in hash)
                    text.Append(b.ToString("x2"));

                return text.ToString();
            }
        }

        internal static string PackageVersion(string packageRoot)
        {
            try
            {
                string path = Path.Combine(packageRoot, "package.json");

                if (!File.Exists(path))
                    return "0.0.0";

                foreach (string line in File.ReadAllLines(path))
                {
                    int index = line.IndexOf("\"version\"", StringComparison.Ordinal);

                    if (index < 0)
                        continue;

                    string[] parts = line.Split('"');

                    if (parts.Length >= 4)
                        return parts[3];
                }
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogWarning("[UMP] Cannot read package version: " + ex.Message);
            }

            return "0.0.0";
        }

        internal static string FindPackageRoot()
        {
            string[] guids = AssetDatabase.FindAssets("UMPSetup t:Script");

            foreach (string guid in guids)
            {
                string assetPath = AssetDatabase.GUIDToAssetPath(guid).Replace("\\", "/");

                if (!assetPath.EndsWith("Editor/UMPSetup.cs", StringComparison.Ordinal))
                    continue;

                string fullPath = Path.GetFullPath(Path.Combine(ProjectRoot, assetPath));

                DirectoryInfo editorDir = Directory.GetParent(fullPath);
                DirectoryInfo packageDir = editorDir != null ? editorDir.Parent : null;

                return packageDir != null ? packageDir.FullName : null;
            }

            return null;
        }

        private static void Report(bool silent, string message)
        {
            UnityEngine.Debug.LogError("[UMP] " + message);

            if (!silent)
                EditorUtility.DisplayDialog("UMP", message, "OK");
        }

        private static void Copy(
            string projectRoot,
            string packageRoot,
            string sourceRelative,
            string destinationRelative,
            string version)
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

            // Every generated script prints its version. A branch that
            // was never re-synced then says so in the build log instead
            // of failing in a way the current templates already fix.
            content = content.Replace("@UMP_VERSION@", version);

            // Skip identical files so Unity does not reimport
            // JenkinsBuild.cs on every sync.
            if (File.Exists(destination) &&
                File.ReadAllText(destination).Replace("\r\n", "\n") == content)
                return;

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
