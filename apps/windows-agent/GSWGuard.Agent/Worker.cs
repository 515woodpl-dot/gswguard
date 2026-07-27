using Microsoft.Extensions.Options;

namespace GswGuard.Agent;

public sealed class Worker(
    ILogger<Worker> logger,
    IOptions<AgentOptions> options,
    YorGuardApiClient apiClient,
    DeviceCredentialStore credentialStore) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var agentOptions = options.Value;
        logger.LogInformation(
            "YorGuard Agent {Version} started in {Environment} mode. No privileged handlers are enabled in this skeleton.",
            agentOptions.Version,
            agentOptions.Environment);

        if (string.IsNullOrWhiteSpace(agentOptions.ApiBaseUrl) || string.IsNullOrWhiteSpace(agentOptions.EnrollmentToken))
        {
            logger.LogInformation("Enrollment receiver is idle: Agent:ApiBaseUrl and Agent:EnrollmentToken are required.");
            await Task.Delay(Timeout.InfiniteTimeSpan, stoppingToken);
            return;
        }

        var credential = credentialStore.Load();
        if (string.IsNullOrWhiteSpace(credential))
        {
            var enrollment = await apiClient.EnrollAsync(agentOptions, stoppingToken);
            credentialStore.Save(enrollment.DeviceCredential);
            credential = enrollment.DeviceCredential;
            logger.LogInformation("YorGuard device enrolled as {DeviceId}.", enrollment.DeviceId);
        }

        while (!stoppingToken.IsCancellationRequested)
        {
            await apiClient.SendHeartbeatAsync(credential, agentOptions.Version, stoppingToken);
            await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
        }
    }
}
