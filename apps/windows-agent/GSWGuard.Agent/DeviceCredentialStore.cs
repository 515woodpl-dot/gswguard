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
        var security = isDirectory
            ? new DirectoryInfo(target).GetAccessControl()
            : new FileInfo(target).GetAccessControl();
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
        if (isDirectory)
            new DirectoryInfo(target).SetAccessControl((DirectorySecurity)security);
        else
            new FileInfo(target).SetAccessControl((FileSecurity)security);
    }
}
