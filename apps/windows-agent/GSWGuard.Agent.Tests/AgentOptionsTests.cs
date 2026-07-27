using GswGuard.Agent;
using Xunit;

namespace GswGuard.Agent.Tests;

public sealed class AgentOptionsTests
{
    [Fact]
    public void Defaults_are_safe_development_values()
    {
        var options = new AgentOptions();

        Assert.Equal("development", options.Environment);
        Assert.Equal("0.1.0", options.Version);
    }
}
