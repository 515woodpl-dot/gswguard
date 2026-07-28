using System.Security.Cryptography;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;

namespace GswGuard.Agent;

public sealed class DeviceCredentialStore
{
    private readonly string path = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "YorGuard",
        "device.credential");

    public string? Load()
    {
        if (!File.Exists(path)) return null;
        var protectedBytes = File.ReadAllBytes(path);
        return Encoding.UTF8.GetString(ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.LocalMachine));
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
