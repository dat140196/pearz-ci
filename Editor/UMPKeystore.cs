#if UNITY_EDITOR
using System;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;

namespace UMP
{
    // Writes Keystores/<package-name>.properties next to Assets/.
    // Jenkins/resolve_keystore.sh looks the signing key up by the
    // Android package name, so the file name is not a free choice.
    internal static class UMPKeystore
    {
        internal const string FolderName = "Keystores";

        internal struct Values
        {
            public string StorePass;
            public string Alias;
            public string AliasPass;

            public bool IsEmpty
            {
                get
                {
                    return string.IsNullOrEmpty(StorePass) &&
                           string.IsNullOrEmpty(Alias) &&
                           string.IsNullOrEmpty(AliasPass);
                }
            }
        }

        // applicationIdentifier of the Android platform - the same
        // value resolve_keystore.sh reads from ProjectSettings.asset.
        internal static string PackageName()
        {
            string identifier = null;

            try
            {
                identifier = PlayerSettings.GetApplicationIdentifier(
                    NamedBuildTarget.Android);
            }
            catch (Exception ex)
            {
                Debug.LogWarning(
                    "[UMP] Cannot read the Android package name: " + ex.Message);
            }

            if (string.IsNullOrEmpty(identifier))
                identifier = Application.identifier;

            return string.IsNullOrEmpty(identifier) ? null : identifier.Trim();
        }

        internal static string FolderPath()
        {
            return Path.Combine(UMPSetup.ProjectRoot, FolderName);
        }

        // null when Player Settings has no package name yet.
        internal static string PropertiesPath()
        {
            string package = PackageName();

            if (string.IsNullOrEmpty(package))
                return null;

            return Path.Combine(FolderPath(), package + ".properties");
        }

        // The key file itself is never generated - it is only reported
        // so the window can say whether the build will actually sign.
        internal static string KeystoreFile()
        {
            string package = PackageName();

            if (string.IsNullOrEmpty(package))
                return null;

            foreach (string extension in new[] { ".keystore", ".jks" })
            {
                string path = Path.Combine(FolderPath(), package + extension);

                if (File.Exists(path))
                    return path;
            }

            return null;
        }

        internal static Values Read(string path)
        {
            var values = new Values();

            if (string.IsNullOrEmpty(path) || !File.Exists(path))
                return values;

            try
            {
                foreach (string line in File.ReadAllLines(path))
                {
                    string text = line.Trim();

                    if (text.Length == 0 || text.StartsWith("#", StringComparison.Ordinal))
                        continue;

                    int separator = text.IndexOf('=');

                    if (separator <= 0)
                        continue;

                    string key = text.Substring(0, separator).Trim();
                    string value = text.Substring(separator + 1).Trim();

                    switch (key)
                    {
                        case "storePass":
                            values.StorePass = value;
                            break;
                        case "alias":
                            values.Alias = value;
                            break;
                        case "aliasPass":
                            values.AliasPass = value;
                            break;
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning(
                    "[UMP] Cannot read " + path + ": " + ex.Message);
            }

            return values;
        }

        // Returns the line shown in the sync dialog. All three fields
        // empty means "no keystore for this project", so nothing is
        // written; an existing file is left alone. Otherwise the file
        // is overwritten, because the window is the source of truth.
        internal static string Sync(Values values)
        {
            values.StorePass = Trim(values.StorePass);
            values.Alias = Trim(values.Alias);
            values.AliasPass = Trim(values.AliasPass);

            if (values.IsEmpty)
                return "Keystore: fields empty, no .properties written.";

            string package = PackageName();

            if (string.IsNullOrEmpty(package))
            {
                Debug.LogError(
                    "[UMP] No Android package name in Player Settings, " +
                    "cannot name the .properties file.");

                return "Keystore: no package name in Player Settings, skipped.";
            }

            string path = PropertiesPath();

            try
            {
                Directory.CreateDirectory(FolderPath());

                var buffer = new StringBuilder();

                buffer.Append("# Generated by UMP - Pearz > SetupJenkin.\n");
                buffer.Append("# Signing values for ").Append(package).Append(".\n");
                buffer.Append("# Keep this repository private: the passwords are plain text.\n");

                Append(buffer, "storePass", values.StorePass);
                Append(buffer, "alias", values.Alias);
                Append(buffer, "aliasPass", values.AliasPass);

                // Read by awk on the Jenkins Mac.
                File.WriteAllText(path, buffer.ToString());
            }
            catch (Exception ex)
            {
                Debug.LogError("[UMP] Cannot write " + path + ": " + ex.Message);

                return "Keystore: writing the .properties file failed, see the console.";
            }

            Debug.Log("[UMP] Wrote " + FolderName + "/" + package + ".properties");

            if (string.IsNullOrEmpty(values.StorePass) ||
                string.IsNullOrEmpty(values.Alias))
            {
                return "Keystore: " + FolderName + "/" + package +
                       ".properties written, but storePass/alias is incomplete.";
            }

            if (KeystoreFile() == null)
            {
                return "Keystore: " + FolderName + "/" + package +
                       ".properties written. Add " + package +
                       ".keystore next to it.";
            }

            return "Keystore: " + FolderName + "/" + package + ".properties written.";
        }

        private static void Append(StringBuilder buffer, string key, string value)
        {
            if (string.IsNullOrEmpty(value))
                return;

            buffer.Append(key).Append('=').Append(value).Append('\n');
        }

        private static string Trim(string value)
        {
            return value == null ? null : value.Trim();
        }
    }
}
#endif
