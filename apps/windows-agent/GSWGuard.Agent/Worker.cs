using Microsoft.Extensions.Options;

namespace GswGuard.Agent;

public sealed class Worker(
    ILogger<Worker> logger,
    IOptions<AgentOptions> options) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        logger.LogInformation(
            "YorGuard Agent {Version} started in {Environment} mode. No privileged handlers are enabled in this skeleton.",
            options.Value.Version,
            options.Value.Environment);

        while (!stoppingToken.IsCancellationRequested)
        {
            await Task.Delay(TimeSpan.FromMinutes(5), stoppingToken);
        }
    }
}
