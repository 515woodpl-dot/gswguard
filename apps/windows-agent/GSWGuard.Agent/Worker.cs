using System.Net;
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
    private static readonly TimeSpan ReportingInterval = TimeSpan.FromMinutes(5);
    private static readonly TimeSpan UnenrolledRetryInterval = TimeSpan.FromMinutes(5);
    private static readonly TimeSpan InitialRetryDelay = TimeSpan.FromSeconds(15);
    private const double MaximumRetryDelaySeconds = 300;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var agentOptions = options.Value;
        logger.LogInformation(
            "YorGuard Agent {Version} started in {Environment} mode. No privileged handlers are enabled.",
            agentOptions.Version,
            agentOptions.Environment);

        if (string.IsNullOrWhiteSpace(agentOptions.ApiBaseUrl))
        {
            logger.LogError("Agent:ApiBaseUrl is required; the receiver is idle.");
            return;
        }

        var retryDelay = InitialRetryDelay;
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // Read the credential from the store on every cycle. It is the
                // durable source of truth. Caching it once before the loop and
                // discarding it on error meant a single transient failure left
                // the service alive but permanently silent: the cached value was
                // cleared, the consumed enrollment token was already gone, and
                // nothing ever re-read the credential from disk again.
                var credential = credentialStore.Load();

                if (string.IsNullOrWhiteSpace(credential))
                {
                    if (string.IsNullOrWhiteSpace(agentOptions.EnrollmentToken))
                    {
                        logger.LogWarning(
                            "This device has no stored credential and no enrollment token. "
                            + "Re-run the YorGuard bootstrap installer to enrol it. Retrying in {Delay}.",
                            UnenrolledRetryInterval);
                        await Task.Delay(UnenrolledRetryInterval, stoppingToken);
                        continue;
                    }

                    var enrollment = await apiClient.EnrollAsync(agentOptions, stoppingToken);
                    credentialStore.Save(enrollment.DeviceCredential);
                    // Only clear the single-use token once the credential is
                    // durably stored, so a crash in between does not strand the
                    // device with neither.
                    enrollmentTokenStore.Clear();
                    credential = enrollment.DeviceCredential;
                    logger.LogInformation("YorGuard device enrolled as {DeviceId}.", enrollment.DeviceId);
                }

                await apiClient.SendHeartbeatAsync(credential, agentOptions.Version, stoppingToken);
                await apiClient.SubmitInventoryAsync(
                    credential,
                    inventoryCollector.Collect(agentOptions),
                    stoppingToken);
                logger.LogInformation("YorGuard heartbeat and inventory submitted.");

                retryDelay = InitialRetryDelay;
                await Task.Delay(ReportingInterval, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (HttpRequestException exception) when (exception.StatusCode == HttpStatusCode.Unauthorized)
            {
                // The server rejected the credential: revoked, or the device row
                // was removed. Retrying cannot fix this, so say so plainly
                // instead of failing quietly on a backoff timer. The stored
                // credential is deliberately left in place for diagnosis.
                logger.LogError(
                    "YorGuard rejected this device's credential (HTTP 401). The device may have been "
                    + "revoked or deleted. Re-run the bootstrap installer to re-enrol. Retrying in {Delay}.",
                    UnenrolledRetryInterval);
                await Task.Delay(UnenrolledRetryInterval, stoppingToken);
            }
            catch (Exception exception)
            {
                // Keep the stored credential. A failure here says nothing about
                // whether the credential is still valid.
                logger.LogWarning(
                    exception,
                    "YorGuard reporting cycle failed; retrying in {Delay}.",
                    retryDelay);
                await Task.Delay(retryDelay, stoppingToken);
                retryDelay = TimeSpan.FromSeconds(
                    Math.Min(retryDelay.TotalSeconds * 2, MaximumRetryDelaySeconds));
            }
        }
    }
}
