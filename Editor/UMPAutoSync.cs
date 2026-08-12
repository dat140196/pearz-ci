#if UNITY_EDITOR
using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace UMP
{
    // Syncs the Jenkins files by itself after the package is
    // installed or updated. The window button stays as a fallback.
    [InitializeOnLoad]
    internal static class UMPAutoSync
    {
        // Library is never committed, so a fresh clone syncs once
        // and a package update re-syncs on every machine.
        private const string StateFile = "Library/UMP.sync";

        // One attempt per editor session, so a failing sync cannot
        // retry on every domain reload.
        private const string AttemptKey = "UMP.AutoSyncAttempted";

        static UMPAutoSync()
        {
            EditorApplication.delayCall += Check;
        }

        private static void Check()
        {
            // Never touch the workspace during a Jenkins build.
            if (Application.isBatchMode)
                return;

            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                EditorApplication.delayCall += Check;
                return;
            }

            if (EditorApplication.isPlayingOrWillChangePlaymode)
                return;

            try
            {
                Sync();
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[UMP] Auto sync skipped: " + ex.Message);
            }
        }

        private static void Sync()
        {
            string packageRoot = UMPSetup.FindPackageRoot();

            if (string.IsNullOrEmpty(packageRoot))
                return;

            string signature = UMPSetup.Signature(packageRoot);
            string statePath = Path.Combine(UMPSetup.ProjectRoot, StateFile);

            bool upToDate =
                File.Exists(statePath) &&
                File.ReadAllText(statePath).Trim() == signature &&
                !UMPSetup.FilesMissing();

            if (upToDate)
                return;

            if (SessionState.GetBool(AttemptKey, false))
                return;

            SessionState.SetBool(AttemptKey, true);

            Debug.Log(
                "[UMP] Package installed or updated (v" +
                UMPSetup.PackageVersion(packageRoot) +
                ") - syncing Jenkins files...");

            if (!UMPSetup.Sync(true))
                return;

            Directory.CreateDirectory(Path.GetDirectoryName(statePath));

            File.WriteAllText(statePath, signature);
        }
    }
}
#endif
