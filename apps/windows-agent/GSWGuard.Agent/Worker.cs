using Microsoft.Extensions.Options;

namespace GswGuard.Agent;

public sealed class Worker(
    ILogger<Worker> logger,
    IOptions<AgentOptions> options,
    YorGuardApiClient apiClient,
    DeviceCredentialStore credentialStore,
    EnrollmentTokenStore enrollmentTokenStore,
    WindowsInventoryCollector inventoryCollector) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var agentOptions = options.Value;
        logger.LogInformation(
            "YorGuard Agent {Version} started in {Environment} mode. No privileged handlers are enabled in this skeleton.",
            agentOptions.Version,
            agentOptions.Environment);

        if (string.IsNullOrWhiteSpace(agentOptions.ApiBaseUrl))
        {
            logger.LogInformation("Enrollment receiver is idle: Agent:ApiBaseUrl is required.");
            await Task.Delay(Timeout.InfiniteTimeSpan, stoppingToken);
            return;
        }

        var credential = credentialStore.Load();
        var retryDelay = TimeSpan.FromSeconds(15);
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(credential))
                {
                    if (string.IsNullOrWhiteSpace(agentOptions.EnrollmentToken))
                    {
                        logger.LogWarning("No device credential or enrollment token is configured; retrying later.");
                        await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
                        continue;
                    }
                    var enrollment = await apiClient.EnrollAsync(agentOptions, stoppingToken);
                    credentialStore.Save(enrollment.DeviceCredential);
                    enrollmentTokenStore.Clear();
                    credential = enrollment.DeviceCredential;
                    logger.LogInformation("YorGuard device enrolled as {DeviceId}.", enrollment.DeviceId);
                }

                await apiClient.SendHeartbeatAsync(credential, agentOptions.Version, stoppingToken);
                await apiClient.SubmitInventoryAsync(
                    credential,
                    inventoryCollector.Collect(agentOptions),
                    stoppingToken);
                logger.LogInformation("YorGuard inventory submitted successfully.");
                retryDelay = TimeSpan.FromSeconds(15);
                await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (HttpRequestException exception)
            {
                logger.LogWarning(exception, "YorGuard API unavailable; retrying in {Delay}.", retryDelay);
                await Task.Delay(retryDelay, stoppingToken);
                retryDelay = TimeSpan.FromSeconds(Math.Min(retryDelay.TotalSeconds * 2, 300));
            }
            catch (Exception exception)
            {
                logger.LogError(exception, "YorGuard receiver cycle failed; retrying in {Delay}.", retryDelay);
                credential = null;
                await Task.Delay(retryDelay, stoppingToken);
                retryDelay = TimeSpan.FromSeconds(Math.Min(retryDelay.TotalSeconds * 2, 300));
            }
        }
    }
}
