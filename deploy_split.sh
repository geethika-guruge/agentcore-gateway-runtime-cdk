#!/bin/bash
set -e

REGION="ap-southeast-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🚀 Deploying base stack with ECR repository..."
cdk deploy agentcore-mcp-demo-base --require-approval never

echo ""
echo "📦 Getting ECR repository URI..."
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name agentcore-mcp-demo-base \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
    --output text)

echo "ECR Repository: $ECR_URI"

echo ""
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

echo ""
echo "🏗️  Building Docker image..."
cd docker-image
docker buildx build --platform linux/arm64 -t $ECR_URI:latest .

echo ""
echo "⬆️  Pushing Docker image to ECR..."
docker push $ECR_URI:latest

cd ..

echo ""
echo "🚀 Deploying main stack..."
cdk deploy agentcore-mcp-demo-l1 --require-approval never

echo ""
echo "✅ Deployment complete!"
