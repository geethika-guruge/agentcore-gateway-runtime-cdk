#!/bin/bash
set -e

echo "Extracting base stack outputs..."
ECR_URI=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' --output text)
RUNTIME_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`RuntimeRoleArn`].OutputValue' --output text)
GATEWAY_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`GatewayRoleArn`].OutputValue' --output text)
OUTBOUND_POOL_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`OutboundUserPoolId`].OutputValue' --output text)
INBOUND_POOL_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`InboundUserPoolId`].OutputValue' --output text)
M2M_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`M2MClientId`].OutputValue' --output text)
INBOUND_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`InboundClientId`].OutputValue' --output text)

echo "Deploying runtime stack..."
cdk deploy M2MAuthRuntimeStack --app 'python3 app_runtime.py' --require-approval never \
  -c ecr_uri=$ECR_URI \
  -c runtime_role_arn=$RUNTIME_ROLE_ARN \
  -c gateway_role_arn=$GATEWAY_ROLE_ARN \
  -c outbound_pool_id=$OUTBOUND_POOL_ID \
  -c inbound_pool_id=$INBOUND_POOL_ID \
  -c m2m_client_id=$M2M_CLIENT_ID \
  -c inbound_client_id=$INBOUND_CLIENT_ID

echo ""
echo "Deployment complete!"
