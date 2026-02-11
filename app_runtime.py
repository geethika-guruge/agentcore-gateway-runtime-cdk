#!/usr/bin/env python3
import aws_cdk as cdk
import sys
from runtime_stack import RuntimeStack
import boto3

app = cdk.App()

project_name = app.node.try_get_context("project_name") or "m2m-auth-demo"
region = app.node.try_get_context("region") or "ap-southeast-2"

# Get base stack outputs from context
ecr_uri = app.node.try_get_context("ecr_uri")
runtime_role_arn = app.node.try_get_context("runtime_role_arn")
gateway_role_arn = app.node.try_get_context("gateway_role_arn")
outbound_pool_id = app.node.try_get_context("outbound_pool_id")
inbound_pool_id = app.node.try_get_context("inbound_pool_id")
m2m_client_id = app.node.try_get_context("m2m_client_id")
inbound_client_id = app.node.try_get_context("inbound_client_id")

if not all([ecr_uri, runtime_role_arn, gateway_role_arn, outbound_pool_id, inbound_pool_id, m2m_client_id, inbound_client_id]):
    print("ERROR: Missing required context parameters. Run deploy_base.sh first.")
    sys.exit(1)

# Get M2M client secret from Cognito
cognito = boto3.client("cognito-idp", region_name=region)
response = cognito.describe_user_pool_client(UserPoolId=outbound_pool_id, ClientId=m2m_client_id)
m2m_client_secret = response["UserPoolClient"]["ClientSecret"]

# Deploy runtime stack
runtime_stack = RuntimeStack(
    app,
    "M2MAuthRuntimeStack",
    project_name=project_name,
    ecr_uri=ecr_uri,
    runtime_role_arn=runtime_role_arn,
    gateway_role_arn=gateway_role_arn,
    outbound_pool_id=outbound_pool_id,
    inbound_pool_id=inbound_pool_id,
    m2m_client_id=m2m_client_id,
    inbound_client_id=inbound_client_id,
    m2m_client_secret=m2m_client_secret,
    env=cdk.Environment(region=region),
)

app.synth()
