using System.Diagnostics;
using System.Security.AccessControl;
using System.Security.Principal;
using System.ServiceProcess;
using System.Text.Json;
using System.Text.Json.Nodes;

const string defaultApiBaseUrl = "https://gsw.tail8a6b99.ts.net:8443";
const string defaultInstallDirectory = @"C:\Program Files\YorGuard\Agent";
const string defaultServiceName = "YorGuardAgent";
const string defaultReleaseBaseUrl = "https://github.com/515woodpl-dot/gswguard/releases";

var arguments = ParseArguments(args);
if (!IsAdministrator())
{
    Console.Error.WriteLine("YorGuard enrollment must run from an Administrator console.");
    return 1;
}

var installDirectory = Get(arguments, "install-directory", defaultInstallDirectory);
var serviceName = Get(arguments, "service-name", defaultServiceName);
var apiBaseUrl = Get(arguments, "api-base-url", defaultApiBaseUrl).TrimEnd('/');
var releaseBaseUrl = Get(arguments, "release-base-url", defaultReleaseBaseUrl).TrimEnd('/');
var settingsPath = Path.Combine(installDirectory, "appsettings.json");
if (!Uri.TryCreate(apiBaseUrl, UriKind.Absolute, out var apiUri) || apiUri.Scheme != Uri.UriSchemeHttps)
{
    Console.Error.WriteLine("ApiBaseUrl must be an absolute https:// URL.");
    return 1;
}
if (!Uri.TryCreate(releaseBaseUrl, UriKind.Absolute, out var releaseUri) || releaseUri.Scheme != Uri.UriSchemeHttps)
{
    Console.Error.WriteLine("ReleaseBaseUrl must be an absolute https:// URL.");
    return 1;
}

var token = Get(arguments, "enrollment-token", "");
if (string.IsNullOrWhiteSpace(token))
{
    token = ReadHiddenToken();
}

if (string.IsNullOrWhiteSpace(token) || token.Length < 20)
{
    Console.Error.WriteLine("A valid one-time enrollment token is required.");
    return 1;
}

if (!File.Exists(settingsPath))
{
    Console.Error.WriteLine($"Agent settings were not found at {settingsPath}. Install the MSI first.");
    return 1;
}

try
{
    StopService(serviceName);
    var root = JsonNode.Parse(File.ReadAllText(settingsPath))?.AsObject()
        ?? throw new InvalidOperationException("Agent settings are not valid JSON.");
    var agent = root["Agent"] as JsonObject ?? new JsonObject();
    root["Agent"] = agent;
    agent["Environment"] = "production";
    agent["ApiBaseUrl"] = apiBaseUrl;
    agent["EnrollmentToken"] = token;
    agent["DeviceName"] = Environment.MachineName;
    agent["Version"] = ReadVersion(installDirectory);

    var temporaryPath = settingsPath + ".tmp";
    File.WriteAllText(temporaryPath, root.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
    RestrictToServiceAccounts(temporaryPath, isDirectory: false);
    File.Move(temporaryPath, settingsPath, overwrite: true);
    RestrictToServiceAccounts(settingsPath, isDirectory: false);

    StartService(serviceName);
    InstallUpdater(installDirectory, serviceName, releaseBaseUrl);
    Console.WriteLine("YorGuard enrollment configuration saved and agent service started.");
    Console.WriteLine("The one-time token will be removed after successful enrollment.");
    return 0;
}
catch (Exception exception)
{
    Console.Error.WriteLine($"YorGuard enrollment failed: {exception.Message}");
    return 1;
}

static Dictionary<string, string> ParseArguments(string[] args)
{
    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    for (var index = 0; index < args.Length; index++)
    {
        if (!args[index].StartsWith("--", StringComparison.Ordinal)) continue;
        var key = args[index][2..];
        values[key] = index + 1 < args.Length && !args[index + 1].StartsWith("--", StringComparison.Ordinal)
            ? args[++index]
            : "true";
    }
    return values;
}

static string Get(IReadOnlyDictionary<string, string> values, string key, string fallback) =>
    values.TryGetValue(key, out var value) ? value : fallback;

static string ReadHiddenToken()
{
    Console.Write("Enrollment token: ");
    var characters = new List<char>();
    ConsoleKeyInfo key;
    do
    {
        key = Console.ReadKey(intercept: true);
        if (key.Key == ConsoleKey.Backspace && characters.Count > 0)
        {
            characters.RemoveAt(characters.Count - 1);
        }
        else if (key.Key != ConsoleKey.Enter && !char.IsControl(key.KeyChar))
        {
            characters.Add(key.KeyChar);
        }
    } while (key.Key != ConsoleKey.Enter);
    Console.WriteLine();
    return new string(characters.ToArray());
}

static bool IsAdministrator()
{
    using var identity = WindowsIdentity.GetCurrent();
    var principal = new WindowsPrincipal(identity);
    return principal.IsInRole(WindowsBuiltInRole.Administrator);
}

static string ReadVersion(string installDirectory)
{
    var versionPath = Path.Combine(installDirectory, "version.txt");
    return File.Exists(versionPath) ? File.ReadAllText(versionPath).Trim() : "0.1.0";
}

static void StopService(string serviceName)
{
    using var service = new ServiceController(serviceName);
    if (service.Status == ServiceControllerStatus.Stopped) return;
    service.Stop();
    service.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(30));
}

static void StartService(string serviceName)
{
    using var service = new ServiceController(serviceName);
    service.Start();
    service.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(30));
}

static void InstallUpdater(string installDirectory, string serviceName, string releaseBaseUrl)
{
    var updaterPath = Path.Combine(installDirectory, "update-windows-agent.ps1");
    if (!File.Exists(updaterPath))
    {
        throw new FileNotFoundException("The signed updater script was not installed.", updaterPath);
    }

    var updaterCommand = $"powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"{updaterPath}\" "
        + $"-InstallDirectory \"{installDirectory}\" -ReleaseBaseUrl \"{releaseBaseUrl}\" "
        + $"-ServiceName \"{serviceName}\"";
    using var process = Process.Start(new ProcessStartInfo
    {
        FileName = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "schtasks.exe"),
        UseShellExecute = false,
        RedirectStandardError = true,
        RedirectStandardOutput = true,
        ArgumentList = { "/Create", "/TN", "YorGuardAgentUpdater", "/SC", "HOURLY", "/MO", "6", "/RU", "SYSTEM", "/F", "/TR", updaterCommand },
    }) ?? throw new InvalidOperationException("Could not start schtasks.exe.");
    process.WaitForExit();
    if (process.ExitCode != 0)
    {
        throw new InvalidOperationException($"Updater task registration failed: {process.StandardError.ReadToEnd().Trim()}");
    }
}

static void RestrictToServiceAccounts(string target, bool isDirectory)
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

static void ApplyServiceAccountAccess(FileSystemSecurity security)
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
