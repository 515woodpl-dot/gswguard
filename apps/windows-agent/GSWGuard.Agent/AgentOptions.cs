using System.ComponentModel.DataAnnotations;

namespace GswGuard.Agent;

public sealed class AgentOptions
{
    public const string SectionName = "Agent";

    [Required, MinLength(1)]
    public string Environment { get; init; } = "development";

    [Required, MinLength(1)]
    public string Version { get; init; } = "0.1.0";

    public string ApiBaseUrl { get; init; } = "";

    public string EnrollmentToken { get; init; } = "";

    public string DeviceName { get; init; } = Environment.MachineName;

    public string Manufacturer { get; init; } = "";

    public string Model { get; init; } = "";

    public string SerialNumber { get; init; } = "";
}
