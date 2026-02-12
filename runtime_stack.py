from aws_cdk import Stack, CfnOutput, aws_bedrockagentcore as agentcore, CustomResource, aws_lambda as lambda_, aws_iam as iam, custom_resources as cr, Duration
from constructs import Construct


class RuntimeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        ecr_uri: str,
        runtime_role_arn: str,
        gateway_role_arn: str,
        outbound_pool_id: str,
        inbound_pool_id: str,
        m2m_client_id: str,
        inbound_client_id: str,
        m2m_client_secret: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # OAuth2 Credential Provider (Custom Resource)
        oauth_handler = lambda_.Function(
            self,
            "OAuth2ProviderHandler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="oauth_provider_handler.handler",
            code=lambda_.Code.from_asset("lambda"),
            timeout=Duration.seconds(60),
            initial_policy=[
                iam.PolicyStatement(
                    actions=[
                        "bedrock-agentcore:CreateOAuth2CredentialProvider",
                        "bedrock-agentcore:DeleteOAuth2CredentialProvider",
                        "bedrock-agentcore:CreateTokenVault",
                        "secretsmanager:CreateSecret",
                        "secretsmanager:DeleteSecret",
                        "secretsmanager:PutSecretValue",
                    ],
                    resources=["*"],
                )
            ],
        )

        oauth_provider = CustomResource(
            self,
            "OAuth2Provider",
            service_token=oauth_handler.function_arn,
            properties={
                "Name": f"{project_name}-m2m-oauth2-provider",
                "CredentialProviderVendor": "CustomOauth2",
                "ClientId": m2m_client_id,
                "ClientSecret": m2m_client_secret,
                "DiscoveryUrl": f"https://cognito-idp.{self.region}.amazonaws.com/{outbound_pool_id}/.well-known/openid-configuration",
            },
        )

        oauth_provider_arn = oauth_provider.get_att_string("CredentialProviderArn")

        # Workload Identity for Gateway
        workload_identity = agentcore.CfnWorkloadIdentity(
            self,
            "WorkloadIdentity",
            name=f"{project_name}-gateway-identity",
            allowed_resource_oauth2_return_urls=["https://localhost/callback", "https://localhost:3000/callback"],
        )

        # Agent Runtime
        agent_runtime = agentcore.CfnRuntime(
            self,
            "AgentRuntime",
            agent_runtime_name=project_name.replace("-", "_") + "_mcp_server",
            description="MCP Server with OAuth M2M authentication",
            role_arn=runtime_role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(container_uri=f"{ecr_uri}:latest")
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="MCP",
            authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{outbound_pool_id}/.well-known/openid-configuration",
                    allowed_clients=[m2m_client_id],
                )
            ),
            environment_variables={"LOG_LEVEL": "INFO", "ENVIRONMENT": "dev"},
        )

        # Gateway
        gateway = agentcore.CfnGateway(
            self,
            "Gateway",
            name=f"{project_name}-gateway",
            role_arn=gateway_role_arn,
            protocol_type="MCP",
            authorizer_type="CUSTOM_JWT",
            authorizer_configuration=agentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{inbound_pool_id}/.well-known/openid-configuration",
                    allowed_clients=[inbound_client_id],
                )
            ),
            protocol_configuration=agentcore.CfnGateway.GatewayProtocolConfigurationProperty(
                mcp=agentcore.CfnGateway.MCPGatewayConfigurationProperty(
                    instructions="M2M OAuth authenticated MCP Gateway",
                    search_type="SEMANTIC",
                    supported_versions=["2025-03-26"],
                )
            ),
            exception_level="DEBUG",
            description="AgentCore Gateway with M2M OAuth authentication",
        )

        # Gateway Target (without OAuth - will need manual configuration)
        runtime_endpoint_arn = f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/{agent_runtime.ref}/runtime-endpoint/DEFAULT"
        import urllib.parse
        escaped_arn = urllib.parse.quote(runtime_endpoint_arn, safe='')
        runtime_endpoint = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{escaped_arn}/invocations"
        
        gateway_target = agentcore.CfnGatewayTarget(
            self,
            "GatewayTarget",
            name=f"{project_name}-mcp-target",
            gateway_identifier=gateway.ref,
            description="MCP Server target - OAuth credentials need manual configuration",
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    mcp_server=agentcore.CfnGatewayTarget.McpServerTargetConfigurationProperty(
                        endpoint=runtime_endpoint
                    )
                )
            ),
        )

        # Outputs
        CfnOutput(self, "RuntimeArn", value=agent_runtime.ref)
        CfnOutput(self, "GatewayId", value=gateway.ref)
        CfnOutput(self, "GatewayTargetId", value=gateway_target.ref)
        CfnOutput(self, "OAuth2ProviderArn", value=oauth_provider_arn)
