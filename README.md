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
├── app.py                      # CDK app entry point
├── stack.py                    # Unified stack with all resources
├── deploy.sh                   # Single deployment script
├── docker-image/               # MCP Server Docker image source
└── cdk.json                    # CDK configuration
```

## Prerequisites

- AWS CLI configured
- AWS CDK CLI installed
- Docker with buildx support
- Python 3.9+
- Node.js (for CDK)

## Deployment

```bash
cd gateway-runtime
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Deploy everything (stack + Docker image)
./deploy.sh
```

This will:
- Create ECR repository
- Create Cognito User Pools (inbound and outbound)
- Create IAM roles with ECR permissions
- Deploy AgentRuntime with MCP Server
- Create Gateway with JWT authentication
- Create OAuth2 Credential Provider
- Create GatewayTarget with OAuth credentials
- Build and push Docker image to ECR

## Stack Outputs

- `ECRRepositoryUri`: Docker image repository
- `InboundUserPoolId`: User authentication pool
- `InboundClientId`: User authentication client
- `OutboundUserPoolId`: M2M authentication pool
- `M2MClientId`: M2M client credentials
- `GatewayId`: Gateway identifier
- `RuntimeArn`: AgentRuntime identifier
- `OAuth2ProviderArn`: OAuth credential provider ARN
- `InboundTokenEndpoint`: Token endpoint for user authentication
- `OutboundTokenEndpoint`: Token endpoint for M2M authentication

## Configuration

Edit `cdk.json` to customize:
- `project_name`: Project prefix (default: m2m-auth-demo)
- `region`: AWS region (default: ap-southeast-2)

## Key Changes from Previous Version

This version uses L2 constructs from `aws_cdk.aws_bedrock_agentcore_alpha` instead of L1 CloudFormation constructs, which resolves the GatewayTarget deployment issues:

- Uses `Runtime` instead of `CfnRuntime`
- Uses `Gateway` instead of `CfnGateway`
- Uses `gateway.add_mcp_server_target()` instead of `CfnGatewayTarget`
- Uses `GatewayCredentialProvider.from_oauth_identity_arn()` for OAuth configuration
- Single unified stack instead of split base/runtime stacks

## Cognito Scopes

The outbound Cognito User Pool defines one scope for MCP server access:
- `mcp-server/tools.execute`: Execute tools on MCP server

## Cleanup

```bash
aws cloudformation delete-stack --stack-name M2MAuthStack --region ap-southeast-2
```

## License

MIT
