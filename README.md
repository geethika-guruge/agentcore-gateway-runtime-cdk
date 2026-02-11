# M2M Auth Gateway - CDK Deployment Guide

Python CDK stack deploying AgentCore Gateway with M2M OAuth authentication.

## Architecture

```
User → Cognito A (JWT) → Gateway → Cognito B (OAuth M2M) → MCP Server Runtime (ECR)
```

- **Inbound**: Cognito User Pool with JWT authentication
- **Outbound**: Cognito User Pool with OAuth2 client_credentials grant
- **Gateway**: AgentCore Gateway (MCP protocol)
- **Runtime**: AgentCore Runtime hosting containerized MCP Server

---

## Prerequisites

- AWS CLI configured with credentials
- Python 3.8+
- Docker with buildx support
- AWS CDK CLI: `npm install -g aws-cdk`

---

## Deployment Steps

### 1. Setup Python Environment

```bash
cd gateway-runtime
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap aws://ACCOUNT-ID/ap-southeast-2
```

### 3. Initial Deploy (Creates ECR Repository)

```bash
cdk deploy
```

**Note**: This will fail at the AgentRuntime resource because the ECR image doesn't exist yet. This is expected.

### 4. Build and Push Docker Image

After the initial deploy creates the ECR repository:

```bash
# Get ECR repository URI from stack outputs
export ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name M2MAuthGatewayStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
  --output text \
  --region ap-southeast-2)

# Login to ECR
aws ecr get-login-password --region ap-southeast-2 | \
  docker login --username AWS --password-stdin $ECR_URI

# Build and push (from parent directory containing agent/ folder)
cd ../agentcore-gateway-runtime-m2m-auth-demo/agent
docker buildx build --platform linux/arm64 -t ${ECR_URI}:latest --push .
```

### 5. Complete Deployment

```bash
cd ../../gateway-runtime
cdk deploy
```

This will successfully create all resources including the AgentRuntime.

---

## Configuration

Edit `cdk.json` to customize:

```json
{
  "context": {
    "project_name": "m2m-auth-demo",
    "region": "ap-southeast-2"
  }
}
```

---

## Stack Outputs

After successful deployment:

| Output | Description |
|--------|-------------|
| `InboundUserPoolId` | Cognito pool for user authentication |
| `InboundClientId` | Client ID for user login |
| `OutboundUserPoolId` | Cognito pool for M2M authentication |
| `M2MClientId` | Client ID for gateway→runtime auth |
| `ECRRepositoryUri` | Container registry URI |
| `GatewayId` | AgentCore Gateway identifier |

---

## Testing

### Create Test User

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <InboundUserPoolId> \
  --username testuser \
  --user-attributes Name=email,Value=test@example.com \
  --temporary-password TempPass123! \
  --region ap-southeast-2
```

### Get User Token

```bash
aws cognito-idp admin-initiate-auth \
  --user-pool-id <InboundUserPoolId> \
  --client-id <InboundClientId> \
  --auth-flow ADMIN_USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=testuser,PASSWORD=<password> \
  --region ap-southeast-2
```

---

## Cleanup

```bash
cdk destroy
```

**Note**: ECR repository is configured with `empty_on_delete=True` for automatic cleanup.

---

## Troubleshooting

**Issue**: AgentRuntime creation fails  
**Solution**: Ensure Docker image is pushed to ECR before final deployment

**Issue**: Docker build fails  
**Solution**: Verify `agent/` directory exists with Dockerfile, mcp_server.py, requirements.txt

**Issue**: Authentication errors  
**Solution**: Check Cognito client IDs match in authorizer configurations
