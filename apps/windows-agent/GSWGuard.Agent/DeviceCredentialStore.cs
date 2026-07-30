using System.Security.Cryptography;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;

namespace GswGuard.Agent;

public sealed class DeviceCredentialStore(ILogger<DeviceCredentialStore> logger)
{
    private readonly string path = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "YorGuard",
        "device.credential");

    /// <summary>
    /// Return the stored device credential, or null when there is none usable.
    /// </summary>
    /// <remarks>
    /// A blob that cannot be decrypted - DPAPI machine key rotated, disk image
    /// restored onto different hardware, file truncated - is reported as absent
    /// rather than thrown. Letting the exception escape took down the whole
    /// service, because this is called from the worker loop and an unhandled
    /// exception in a BackgroundService stops the host by default.
    /// </remarks>
    public string? Load()
    {
        if (!File.Exists(path)) return null;
        try
        {
            var protectedBytes = File.ReadAllBytes(path);
            return Encoding.UTF8.GetString(ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.LocalMachine));
        }
        catch (Exception exception) when (exception is CryptographicException or IOException or UnauthorizedAccessException)
        {
            // Never log the path contents or the exception's data, only its kind.
            logger.LogError(
                "The stored YorGuard device credential could not be read ({Reason}). "
                + "Treating this device as unenrolled; re-run the bootstrap installer to re-enrol it.",
                exception.GetType().Name);
            return null;
        }
    }

    public void Save(string credential)
    {
        var directory = Path.GetDirectoryName(path)!;
        Directory.CreateDirectory(directory);
        RestrictToServiceAccounts(directory, isDirectory: true);
        var protectedBytes = ProtectedData.Protect(Encoding.UTF8.GetBytes(credential), null, DataProtectionScope.LocalMachine);
        var temporaryPath = path + ".tmp";
        File.WriteAllBytes(temporaryPath, protectedBytes);
        RestrictToServiceAccounts(temporaryPath, isDirectory: false);
        File.Move(temporaryPath, path, overwrite: true);
        RestrictToServiceAccounts(path, isDirectory: false);
    }

    private static void RestrictToServiceAccounts(string target, bool isDirectory)
    {
        if (isDirectory)
        {
            var directory = new DirectoryInfo(target);
            var security = directory.GetAccessControl();
            ApplyServiceAccountAccess(security);
            directory.SetAccessControl(security);
            return;
        }

        var file = new FileInfo(target);
        var fileSecurity = file.GetAccessControl();
        ApplyServiceAccountAccess(fileSecurity);
        file.SetAccessControl(fileSecurity);
    }

    private static void ApplyServiceAccountAccess(FileSystemSecurity security)
    {
        security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
        security.SetAccessRule(new FileSystemAccessRule(
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
            FileSystemRights.FullControl,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
            PropagationFlags.None,
            AccessControlType.Allow));
        security.AddAccessRule(new FileSystemAccessRule(
            new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null),
            FileSystemRights.FullControl,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
            PropagationFlags.None,
            AccessControlType.Allow));
    }
}
