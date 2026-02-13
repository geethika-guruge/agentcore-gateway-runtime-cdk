import aws_cdk as cdk
from aws_cdk import (
    aws_iam as iam,
    aws_cognito as cognito,
    aws_bedrockagentcore as bedrockagentcore,
)
from constructs import Construct


class MinimalTestStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # IAM Role
        role = iam.Role(
            self,
            "TestRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
        )

        # Cognito User Pool
        pool = cognito.UserPool(
            self,
            "TestPool",
            user_pool_name="test-pool",
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        client = pool.add_client(
            "TestClient",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_password=True),
        )

        # Test Gateway only
        gateway = bedrockagentcore.CfnGateway(
            self,
            "TestGateway",
            name="test-gateway",
            authorizer_type="CUSTOM_JWT",
            protocol_type="MCP",
            role_arn=role.role_arn,
            authorizer_configuration=bedrockagentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=bedrockagentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{pool.user_pool_id}/.well-known/openid-configuration",
                    allowed_clients=[client.user_pool_client_id],
                )
            ),
        )

        cdk.CfnOutput(self, "GatewayId", value=gateway.attr_gateway_identifier)
