using GswGuard.Agent;
using Microsoft.Extensions.Options;

var builder = Host.CreateApplicationBuilder(args);

builder.Services
    .AddOptions<AgentOptions>()
    .Bind(builder.Configuration.GetSection(AgentOptions.SectionName))
    .ValidateDataAnnotations()
    .ValidateOnStart();
builder.Services.AddHttpClient<YorGuardApiClient>((serviceProvider, client) =>
{
    var options = serviceProvider.GetRequiredService<IOptions<AgentOptions>>().Value;
    if (!string.IsNullOrWhiteSpace(options.ApiBaseUrl))
    {
        client.BaseAddress = new Uri(options.ApiBaseUrl.TrimEnd('/') + "/");
    }
    client.Timeout = TimeSpan.FromSeconds(20);
});
builder.Services.AddSingleton<DeviceCredentialStore>();
builder.Services.AddSingleton<EnrollmentTokenStore>();
builder.Services.AddSingleton<WindowsInventoryCollector>();
builder.Services.AddWindowsService(options => options.ServiceName = "YorGuard Agent");
builder.Services.AddHostedService<Worker>();

var host = builder.Build();
await host.RunAsync();
