import json
import boto3
import urllib.parse
from botocore.exceptions import ClientError

client = boto3.client('bedrock-agentcore')

def handler(event, context):
    print(f"Event: {json.dumps(event)}")
    
    request_type = event['RequestType']
    props = event['ResourceProperties']
    
    try:
        if request_type == 'Create':
            return create_gateway_target(props, event)
        elif request_type == 'Update':
            return update_gateway_target(props, event)
        elif request_type == 'Delete':
            return delete_gateway_target(props, event)
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def create_gateway_target(props, event):
    params = {
        'name': props['Name'],
        'gatewayIdentifier': props['GatewayIdentifier'],
        'description': props.get('Description', ''),
        'targetConfiguration': {
            'mcp': {
                'mcpServer': {
                    'endpoint': props['Endpoint']
                }
            }
        }
    }
    
    # Add OAuth credential provider if provided
    if 'OAuthProviderArn' in props and 'OAuthScopes' in props:
        params['credentialProviderConfigurations'] = [{
            'credentialProviderType': 'OAuth',
            'credentialProvider': {
                'oauthCredentialProvider': {
                    'providerArn': props['OAuthProviderArn'],
                    'scopes': props['OAuthScopes']
                }
            }
        }]
    
    response = client.create_gateway_target(**params)
    
    physical_id = response['gatewayTargetId']
    
    return {
        'PhysicalResourceId': physical_id,
        'Data': {
            'GatewayTargetId': physical_id,
            'GatewayTargetArn': response.get('gatewayTargetArn', '')
        }
    }

def update_gateway_target(props, event):
    physical_id = event['PhysicalResourceId']
    
    params = {
        'gatewayTargetIdentifier': physical_id,
        'description': props.get('Description', ''),
        'targetConfiguration': {
            'mcp': {
                'mcpServer': {
                    'endpoint': props['Endpoint']
                }
            }
        }
    }
    
    # Add OAuth credential provider if provided
    if 'OAuthProviderArn' in props and 'OAuthScopes' in props:
        params['credentialProviderConfigurations'] = [{
            'credentialProviderType': 'OAuth',
            'credentialProvider': {
                'oauthCredentialProvider': {
                    'providerArn': props['OAuthProviderArn'],
                    'scopes': props['OAuthScopes']
                }
            }
        }]
    
    response = client.update_gateway_target(**params)
    
    return {
        'PhysicalResourceId': physical_id,
        'Data': {
            'GatewayTargetId': physical_id,
            'GatewayTargetArn': response.get('gatewayTargetArn', '')
        }
    }

def delete_gateway_target(props, event):
    physical_id = event['PhysicalResourceId']
    
    if physical_id == 'NONE':
        return {'PhysicalResourceId': physical_id}
    
    try:
        client.delete_gateway_target(gatewayTargetIdentifier=physical_id)
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceNotFoundException':
            raise
    
    return {'PhysicalResourceId': physical_id}
