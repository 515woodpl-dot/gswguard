using System.Management;
using Microsoft.Win32;

namespace GswGuard.Agent;

public sealed class WindowsInventoryCollector
{
    public Dictionary<string, object?> Collect(AgentOptions options)
    {
        var os = QuerySingle("Win32_OperatingSystem");
        var computer = QuerySingle("Win32_ComputerSystem");
        var bios = QuerySingle("Win32_BIOS");
        var processor = QuerySingle("Win32_Processor");

        var model = Value(computer, "Model") ?? options.Model;
        var manufacturer = Value(computer, "Manufacturer") ?? options.Manufacturer;
        var serial = Value(bios, "SerialNumber") ?? options.SerialNumber;
        var totalMemory = ToLong(Value(computer, "TotalPhysicalMemory"));
        var logicalProcessors = Math.Max(1, (int)ToLong(Value(processor, "NumberOfLogicalProcessors")));

        return new Dictionary<string, object?>
        {
            ["snapshot"] = new Dictionary<string, object?>
            {
                ["platform"] = "windows",
                ["device_name"] = options.DeviceName,
                ["manufacturer"] = string.IsNullOrWhiteSpace(manufacturer) ? "Unknown" : manufacturer,
                ["model"] = string.IsNullOrWhiteSpace(model) ? "Unknown" : model,
                ["serial_number"] = string.IsNullOrWhiteSpace(serial) ? "Unknown" : serial,
                ["os_version"] = Value(os, "Caption") + " " + Value(os, "Version"),
                ["windows"] = new Dictionary<string, object?>
                {
                    ["edition"] = Value(os, "Caption") ?? "Unknown",
                    ["version"] = Value(os, "Version") ?? "Unknown",
                    ["build"] = Value(os, "BuildNumber") ?? "Unknown",
                    ["update_status"] = "not_collected",
                },
                ["cpu"] = new Dictionary<string, object?>
                {
                    ["name"] = Value(processor, "Name") ?? "Unknown",
                    ["logical_processors"] = logicalProcessors,
                },
                ["installed_ram_bytes"] = totalMemory,
                ["storage"] = Query("Win32_LogicalDisk", "DriveType = 3").Select(d => new Dictionary<string, object?>
                {
                    ["name"] = Value(d, "DeviceID") ?? "Unknown",
                    ["capacity_bytes"] = ToLong(Value(d, "Size")),
                    ["free_bytes"] = ToLong(Value(d, "FreeSpace")),
                }).ToList(),
                ["network_adapters"] = Query("Win32_NetworkAdapterConfiguration", "IPEnabled = True").Select(n => new Dictionary<string, object?>
                {
                    ["name"] = Value(n, "Description") ?? "Unknown",
                    ["mac_address"] = Value(n, "MACAddress") ?? "Unknown",
                    ["ip_addresses"] = ArrayValue(n, "IPAddress"),
                }).ToList(),
                ["security"] = new Dictionary<string, object?>
                {
                    ["bitlocker"] = "not_collected",
                    ["firewall"] = "not_collected",
                    ["defender"] = "not_collected",
                    ["secure_boot"] = "not_collected",
                    ["tpm"] = "not_collected",
                    ["automatic_updates"] = "not_collected",
                },
                ["local_accounts"] = Query("Win32_UserAccount", "LocalAccount = True").Select(a => new Dictionary<string, object?>
                {
                    ["name"] = Value(a, "Name") ?? "Unknown",
                    ["account_type"] = "local",
                    ["is_administrator"] = false,
                }).ToList(),
                ["software"] = InstalledSoftware(),
                ["agent_version"] = options.Version,
            },
            ["captured_at"] = DateTimeOffset.UtcNow,
        };
    }

    private static List<ManagementObject> Query(string className, string? condition = null)
    {
        using var searcher = new ManagementObjectSearcher($"select * from {className}{(condition is null ? "" : " where " + condition)}");
        return searcher.Get().Cast<ManagementObject>().ToList();
    }

    private static ManagementObject? QuerySingle(string className) => Query(className).FirstOrDefault();

    private static string? Value(ManagementObject? item, string name) => item?[name]?.ToString()?.Trim();

    private static long ToLong(string? value) => long.TryParse(value, out var result) ? Math.Max(0, result) : 0;

    private static List<string> ArrayValue(ManagementObject item, string name) =>
        (item[name] as string[] ?? Array.Empty<string>()).Where(value => !string.IsNullOrWhiteSpace(value)).Take(16).ToList();

    private static List<Dictionary<string, object?>> InstalledSoftware()
    {
        var result = new List<Dictionary<string, object?>>();
        var locations = new[]
        {
            (RegistryHive.LocalMachine, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (RegistryHive.LocalMachine, @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (RegistryHive.CurrentUser, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        };
        foreach (var (hive, path) in locations)
        {
            using var baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Registry64);
            using var uninstall = baseKey.OpenSubKey(path);
            if (uninstall is null) continue;
            foreach (var name in uninstall.GetSubKeyNames())
            {
                using var item = uninstall.OpenSubKey(name);
                var displayName = item?.GetValue("DisplayName")?.ToString();
                if (string.IsNullOrWhiteSpace(displayName)) continue;
                result.Add(new Dictionary<string, object?>
                {
                    ["name"] = displayName.Trim(),
                    ["publisher"] = item?.GetValue("Publisher")?.ToString(),
                    ["version"] = item?.GetValue("DisplayVersion")?.ToString() ?? "unknown",
                    ["architecture"] = Environment.Is64BitOperatingSystem ? "x64" : "x86",
                    ["install_source"] = "registry",
                });
                if (result.Count >= 2000) return result;
            }
        }
        return result;
    }
}
