using System.Text.Json;
using System.Text.Json.Nodes;

namespace GswGuard.Agent;

public sealed class EnrollmentTokenStore
{
    public void Clear()
    {
        var settingsPath = Path.Combine(AppContext.BaseDirectory, "appsettings.json");
        if (!File.Exists(settingsPath))
        {
            return;
        }

        var root = JsonNode.Parse(File.ReadAllText(settingsPath))?.AsObject()
            ?? throw new InvalidOperationException("Agent settings are not valid JSON.");
        if (root["Agent"] is not JsonObject agent || !agent.Remove("EnrollmentToken"))
        {
            return;
        }

        var json = root.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(settingsPath, json);
    }
}
