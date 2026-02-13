#!/bin/bash
set -e

REGION="ap-southeast-2"
STACK_NAME="agentcore-mcp-demo-l1"

echo "Step 1: Deploy stack to create ECR repository..."
cdk deploy $STACK_NAME --require-approval never || true

echo "Step 2: Get ECR URI..."
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
    --output text 2>/dev/null || \
    aws ecr describe-repositories \
    --repository-names agentcore-mcp-demo-l1-mcp-server \
    --region $REGION \
    --query 'repositories[0].repositoryUri' \
    --output text)

echo "ECR URI: $ECR_URI"

echo "Step 3: Build and push Docker image..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI
cd docker-image
docker buildx build --platform linux/arm64 -t $ECR_URI:latest --push .
cd ..

echo "Step 4: Deploy full stack with image..."
cdk deploy $STACK_NAME --require-approval never

echo "Deployment complete!"
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table
