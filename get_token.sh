#!/bin/bash

USER_POOL_ID="ap-southeast-2_6WN6cJvFa"
CLIENT_ID="2lu2vvr5vvckbv9fofobnocmmn"
REGION="ap-southeast-2"
USERNAME="${1:-test-user}"
PASSWORD="${2}"

if [ -z "$PASSWORD" ]; then
  echo "Usage: $0 [username] <password>"
  echo "Example: $0 test-user MyPassword123!"
  exit 1
fi

echo "Authenticating as $USERNAME..."

RESPONSE=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --region "$REGION" \
  2>&1)

if [ $? -eq 0 ]; then
  ID_TOKEN=$(echo "$RESPONSE" | jq -r '.AuthenticationResult.IdToken')
  ACCESS_TOKEN=$(echo "$RESPONSE" | jq -r '.AuthenticationResult.AccessToken')
  
  echo ""
  echo "✓ Authentication successful!"
  echo ""
  echo "ID Token (use this for Gateway):"
  echo "$ID_TOKEN"
  echo ""
  echo "Access Token:"
  echo "$ACCESS_TOKEN"
else
  echo "✗ Authentication failed:"
  echo "$RESPONSE"
  exit 1
fi
