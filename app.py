#!/usr/bin/env python3
import aws_cdk as cdk
from base_stack import BaseInfraStack

app = cdk.App()

project_name = app.node.try_get_context("project_name") or "m2m-auth-demo"
region = app.node.try_get_context("region") or "ap-southeast-2"

# Deploy base infrastructure first
base_stack = BaseInfraStack(
    app,
    "M2MAuthBaseStack",
    project_name=project_name,
    env=cdk.Environment(region=region),
)

app.synth()
