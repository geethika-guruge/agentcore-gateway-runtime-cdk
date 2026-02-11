#!/bin/bash
set -e

echo "Deploying base infrastructure..."
cdk deploy M2MAuthBaseStack --require-approval never

echo ""
echo "Extracting stack outputs..."
ECR_URI=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' --output text)
RUNTIME_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`RuntimeRoleArn`].OutputValue' --output text)
GATEWAY_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`GatewayRoleArn`].OutputValue' --output text)
OUTBOUND_POOL_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`OutboundUserPoolId`].OutputValue' --output text)
INBOUND_POOL_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`InboundUserPoolId`].OutputValue' --output text)
M2M_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`M2MClientId`].OutputValue' --output text)
INBOUND_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name M2MAuthBaseStack --region ap-southeast-2 --query 'Stacks[0].Outputs[?OutputKey==`InboundClientId`].OutputValue' --output text)

echo "ECR Repository: $ECR_URI"
echo ""
echo "Building and pushing Docker image..."
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin $ECR_URI
docker buildx build --platform linux/arm64 -t $ECR_URI:latest --push ./docker-image

echo ""
echo "Docker image pushed successfully!"
echo ""
echo "To deploy the runtime stack, run:"
echo "./deploy_runtime.sh"
echo ""
echo "Or manually with:"
echo "cdk deploy M2MAuthRuntimeStack --app 'python3 app_runtime.py' \\"
echo "  -c ecr_uri=$ECR_URI \\"
echo "  -c runtime_role_arn=$RUNTIME_ROLE_ARN \\"
echo "  -c gateway_role_arn=$GATEWAY_ROLE_ARN \\"
echo "  -c outbound_pool_id=$OUTBOUND_POOL_ID \\"
echo "  -c inbound_pool_id=$INBOUND_POOL_ID \\"
echo "  -c m2m_client_id=$M2M_CLIENT_ID \\"
echo "  -c inbound_client_id=$INBOUND_CLIENT_ID"
