using System.ComponentModel.DataAnnotations;

namespace GswGuard.Agent;

public sealed class AgentOptions
{
    public const string SectionName = "Agent";

    [Required, MinLength(1)]
    public string Environment { get; init; } = "development";

    [Required, MinLength(1)]
    public string Version { get; init; } = "0.1.0";
}
