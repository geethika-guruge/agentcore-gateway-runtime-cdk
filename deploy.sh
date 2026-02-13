#!/bin/bash
set -e

PROJECT_NAME="${PROJECT_NAME:-m2m-auth-demo}"
REGION="${REGION:-ap-southeast-2}"

echo "Deploying M2M Auth Stack..."
echo "Project: $PROJECT_NAME"
echo "Region: $REGION"

# Get ECR repository URI from stack outputs
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name M2MAuthStack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$ECR_URI" ]; then
    echo "Stack not deployed yet. Deploying for the first time..."
    cdk deploy M2MAuthStack \
        --context project_name=$PROJECT_NAME \
        --context region=$REGION \
        --require-approval never
    
    ECR_URI=$(aws cloudformation describe-stacks \
        --stack-name M2MAuthStack \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
        --output text)
fi

echo "Building and pushing Docker image to $ECR_URI..."

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Build for ARM64 (Graviton)
cd docker-image
docker buildx build --platform linux/arm64 -t $ECR_URI:latest --push .
cd ..

echo "Updating stack with new image..."
cdk deploy M2MAuthStack \
    --context project_name=$PROJECT_NAME \
    --context region=$REGION \
    --require-approval never

echo "Deployment complete!"
echo ""
echo "Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name M2MAuthStack \
    --region $REGION \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table
