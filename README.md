# BedrockAgentCore Gateway with M2M OAuth Authentication (CDK)

AWS CDK implementation of BedrockAgentCore Gateway demonstrating Machine-to-Machine (M2M) OAuth authentication pattern.

## Architecture

```
User → Gateway (JWT Inbound Auth) → MCP Server Runtime (OAuth M2M Outbound Auth)
```

- **Inbound Authentication**: User authenticates with Cognito User Pool A, receives JWT token
- **Gateway**: Validates user JWT, forwards requests to MCP Server
- **Outbound Authentication**: Gateway uses OAuth2 client_credentials flow with Cognito User Pool B to authenticate with MCP Server
- **MCP Server Runtime**: Validates OAuth token, executes MCP tools

## Project Structure

```
.
├── app.py                      # Base stack CDK app
├── app_runtime.py              # Runtime stack CDK app
├── base_stack.py               # Base infrastructure (ECR, Cognito, IAM)
├── runtime_stack.py            # Runtime resources (AgentRuntime, Gateway, OAuth2Provider)
├── deploy_base.sh              # Deploy base infrastructure and Docker image
├── deploy_runtime.sh           # Deploy runtime stack
├── docker-image/               # MCP Server Docker image source
├── lambda/
│   ├── oauth_provider_handler.py      # OAuth2 credential provider custom resource
│   └── gateway_target_handler.py      # GatewayTarget custom resource (unused)
└── cdk.json                    # CDK configuration
```

## Prerequisites

- AWS CLI configured
- AWS CDK CLI installed
- Docker with buildx support
- Python 3.9+
- Node.js (for CDK)

## Deployment

### 1. Deploy Base Infrastructure

```bash
cd gateway-runtime
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Deploy base stack (ECR, Cognito, IAM) and push Docker image
./deploy_base.sh
```

This will:
- Create ECR repository
- Create Cognito User Pools (inbound and outbound)
- Create IAM roles with ECR permissions
- Build and push Docker image to ECR

### 2. Deploy Runtime Stack

```bash
# Deploy runtime stack (AgentRuntime, Gateway, OAuth2Provider)
./deploy_runtime.sh
```

This will:
- Create OAuth2 Credential Provider
- Deploy AgentRuntime with MCP Server
- Create Gateway with JWT authentication
- Attempt to create GatewayTarget (currently fails - see Known Issues)

## Stack Outputs

### Base Stack
- `ECRRepositoryUri`: Docker image repository
- `InboundUserPoolId`: User authentication pool
- `InboundClientId`: User authentication client
- `OutboundUserPoolId`: M2M authentication pool
- `M2MClientId`: M2M client credentials
- `RuntimeRoleArn`: Runtime IAM role
- `GatewayRoleArn`: Gateway IAM role

### Runtime Stack
- `RuntimeArn`: AgentRuntime identifier
- `GatewayId`: Gateway identifier
- `OAuth2ProviderArn`: OAuth credential provider ARN

## Configuration

Edit `cdk.json` to customize:
- `project_name`: Project prefix (default: m2m-auth-demo)
- `region`: AWS region (default: ap-southeast-2)

## Known Issues

### GatewayTarget Deployment

The GatewayTarget resource cannot be deployed via CDK due to a CloudFormation validation issue when including OAuth credential provider configuration:

**Issue**: CloudFormation Early Validation fails when `credential_provider_configurations` includes OAuth scopes
**Workaround**: Deploy without GatewayTarget, or use Terraform (see [terraform implementation](https://github.com/geethika-guruge/agentcore-gateway-runtime-m2m-auth-demo))

**Error**:
```
FAILED, The following hook(s)/validation failed: [AWS::EarlyValidation::PropertyValidation]
```

This appears to be a BedrockAgentCore preview service limitation where OAuth credential provider configuration isn't fully supported in CloudFormation yet.

## Cognito Scopes

The outbound Cognito User Pool defines three scopes for MCP server access:
- `mcp-server/tools.read`: Read tools from MCP server
- `mcp-server/tools.write`: Write tools to MCP server
- `mcp-server/tools.execute`: Execute tools on MCP server

## Cleanup

```bash
# Delete runtime stack
aws cloudformation delete-stack --stack-name M2MAuthRuntimeStack --region ap-southeast-2

# Delete base stack (will also delete ECR images)
aws cloudformation delete-stack --stack-name M2MAuthBaseStack --region ap-southeast-2
```

## Comparison with Terraform

A working Terraform implementation is available at:
https://github.com/geethika-guruge/agentcore-gateway-runtime-m2m-auth-demo

The Terraform version successfully deploys all resources including GatewayTarget with OAuth credentials.

## License

MIT
