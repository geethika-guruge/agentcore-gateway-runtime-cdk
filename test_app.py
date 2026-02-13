#!/usr/bin/env python3
import aws_cdk as cdk
from test_stack import MinimalTestStack

app = cdk.App()

MinimalTestStack(
    app,
    "minimal-test",
    env=cdk.Environment(region="ap-southeast-2"),
)

app.synth()
