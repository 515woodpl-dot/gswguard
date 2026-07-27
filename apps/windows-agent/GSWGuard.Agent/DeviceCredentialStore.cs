using System.Security.Cryptography;
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
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var protectedBytes = ProtectedData.Protect(Encoding.UTF8.GetBytes(credential), null, DataProtectionScope.LocalMachine);
        File.WriteAllBytes(path, protectedBytes);
    }
}
