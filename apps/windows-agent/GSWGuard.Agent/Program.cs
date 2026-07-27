using GswGuard.Agent;
using Microsoft.Extensions.Options;

var builder = Host.CreateApplicationBuilder(args);

builder.Services
    .AddOptions<AgentOptions>()
    .Bind(builder.Configuration.GetSection(AgentOptions.SectionName))
    .ValidateDataAnnotations()
    .ValidateOnStart();
builder.Services.AddWindowsService(options => options.ServiceName = "YorGuard Agent");
builder.Services.AddHostedService<Worker>();

var host = builder.Build();
await host.RunAsync();
