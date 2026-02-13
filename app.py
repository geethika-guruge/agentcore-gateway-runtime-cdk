#!/usr/bin/env python3
import aws_cdk as cdk
from base_stack import BaseStack
from stack import AgentCoreMCPDemoL1Stack

app = cdk.App()

# Base stack with ECR
base_stack = BaseStack(
    app,
    "agentcore-mcp-demo-base",
    stack_name="agentcore-mcp-demo-base",
    env=cdk.Environment(region="ap-southeast-2"),
)

# Main stack with everything else
main_stack = AgentCoreMCPDemoL1Stack(
    app,
    "agentcore-mcp-demo-l1",
    ecr_repository=base_stack.ecr_repository,
    stack_name="agentcore-mcp-demo-l1",
    env=cdk.Environment(region="ap-southeast-2"),
)

main_stack.add_dependency(base_stack)

app.synth()

