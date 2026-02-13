#!/usr/bin/env python3
import aws_cdk as cdk
from stack import AgentCoreMCPDemoStack

app = cdk.App()

AgentCoreMCPDemoStack(
    app,
    "agentcore-mcp-demo",
    env=cdk.Environment(region="ap-southeast-2"),
)

app.synth()
