#!/bin/bash

set -e

REGION="ap-southeast-2"
USERNAME="${1:-test-user}"
PASSWORD="${2:-TestPass123!}"

# Get values from CloudFormation outputs
STACK_NAME="agentcore-mcp-demo"
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`InboundUserPoolId`].OutputValue' \
  --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`InboundClientId`].OutputValue' \
  --output text)

GATEWAY_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`GatewayUrl`].OutputValue' \
  --output text)

if [ -z "$USER_POOL_ID" ] || [ -z "$CLIENT_ID" ] || [ -z "$GATEWAY_URL" ]; then
  echo "✗ Could not find required stack outputs"
  exit 1
fi

echo "========================================="
echo "Step 0: Create test user"
echo "========================================="

# Check if user exists
if aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$USERNAME" \
  --region "$REGION" &>/dev/null; then
  echo "✓ User $USERNAME already exists"
else
  echo "Creating user $USERNAME..."
  aws cognito-idp admin-create-user \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --temporary-password 'TempPass123!' \
    --message-action SUPPRESS \
    --region "$REGION" >/dev/null
  echo "✓ User created"
fi

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username "$USERNAME" \
  --password "$PASSWORD" \
  --permanent \
  --region "$REGION" >/dev/null
echo "✓ Password set"
echo ""

echo "========================================="
echo "Step 1: Authenticate and get token"
echo "========================================="

TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --region "$REGION" \
  --query 'AuthenticationResult.AccessToken' \
  --output text)

echo "✓ Authentication successful!"
echo "Token: ${TOKEN:0:50}..."
echo ""

echo "========================================="
echo "Step 2: List available tools"
echo "========================================="

LIST_RESPONSE=$(curl -s -X POST "$GATEWAY_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')

echo "✓ Available tools:"
echo "$LIST_RESPONSE" | jq '.'
echo ""

echo "========================================="
echo "Step 3: Call a tool"
echo "========================================="

TOOL_NAME=$(echo "$LIST_RESPONSE" | jq -r '.result.tools[0].name // empty')

if [ -z "$TOOL_NAME" ]; then
  echo "✗ No tools found"
  exit 1
fi

echo "Calling tool: $TOOL_NAME"

CALL_RESPONSE=$(curl -s -X POST "$GATEWAY_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"$TOOL_NAME\",\"arguments\":{}}}")

echo "✓ Tool call response:"
echo "$CALL_RESPONSE" | jq '.'
echo ""

echo "========================================="
echo "All steps completed successfully!"
echo "========================================="
