import json
import boto3
import urllib3

http = urllib3.PoolManager()
# Use bedrock-agentcore-control client
client = boto3.client('bedrock-agentcore-control')

def handler(event, context):
    print(f"Event: {json.dumps(event)}")
    
    request_type = event['RequestType']
    props = event['ResourceProperties']
    
    try:
        if request_type == 'Create':
            response = client.create_oauth2_credential_provider(
                name=props['Name'],
                credentialProviderVendor=props['CredentialProviderVendor'],
                oauth2ProviderConfigInput={
                    'customOauth2ProviderConfig': {
                        'clientId': props['ClientId'],
                        'clientSecret': props['ClientSecret'],
                        'oauthDiscovery': {
                            'discoveryUrl': props['DiscoveryUrl']
                        }
                    }
                }
            )
            physical_id = props['Name']  # Use name as physical ID for deletion
            send_response(event, context, 'SUCCESS', {
                'CredentialProviderArn': response['credentialProviderArn'],
                'Name': props['Name']
            }, physical_id)
            
        elif request_type == 'Update':
            physical_id = event['PhysicalResourceId']
            send_response(event, context, 'SUCCESS', {
                'CredentialProviderArn': physical_id
            }, physical_id)
            
        elif request_type == 'Delete':
            physical_id = event['PhysicalResourceId']
            if physical_id != 'NONE':
                try:
                    client.delete_oauth2_credential_provider(
                        name=physical_id
                    )
                except client.exceptions.ResourceNotFoundException:
                    pass
            send_response(event, context, 'SUCCESS', {}, physical_id)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        send_response(event, context, 'FAILED', {}, event.get('PhysicalResourceId', 'NONE'))

def send_response(event, context, status, data, physical_id):
    response_body = {
        'Status': status,
        'Reason': f'See CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': physical_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data
    }
    
    http.request(
        'PUT',
        event['ResponseURL'],
        body=json.dumps(response_body).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
