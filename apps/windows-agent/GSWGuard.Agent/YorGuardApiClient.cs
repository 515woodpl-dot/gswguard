using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace GswGuard.Agent;

public sealed class YorGuardApiClient(HttpClient httpClient)
{
    public async Task<EnrollmentResponse> EnrollAsync(AgentOptions options, CancellationToken cancellationToken)
    {
        using var response = await httpClient.PostAsJsonAsync(
            "/api/v1/devices/enroll",
            new
            {
                token = options.EnrollmentToken,
                device_name = options.DeviceName,
                manufacturer = options.Manufacturer,
                model = options.Model,
                serial_number = options.SerialNumber,
                agent_version = options.Version,
                platform = "windows",
                os_version = Environment.OSVersion.VersionString,
            },
            cancellationToken);
        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<EnrollmentResponse>(cancellationToken))
            ?? throw new InvalidOperationException("YorGuard returned an empty enrollment response.");
    }

    public async Task SendHeartbeatAsync(string credential, string version, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/devices/heartbeat")
        {
            Content = JsonContent.Create(new
            {
                observed_at = DateTimeOffset.UtcNow,
                agent_version = version,
            }),
        };
        request.Headers.Authorization = new("Device", credential);
        using var response = await httpClient.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
    }
}

public sealed record EnrollmentResponse(
    [property: JsonPropertyName("device_id")] Guid DeviceId,
    [property: JsonPropertyName("device_credential")] string DeviceCredential,
    [property: JsonPropertyName("enrolled_at")] DateTimeOffset EnrolledAt);
