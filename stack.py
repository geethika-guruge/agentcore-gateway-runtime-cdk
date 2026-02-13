import os
import aws_cdk as cdk
from aws_cdk import (
    aws_iam as iam,
    aws_cognito as cognito,
    aws_ecr as ecr,
    custom_resources as cr,
)
from aws_cdk.aws_bedrock_agentcore_alpha import (
    AgentRuntimeArtifact,
    Runtime,
    RuntimeAuthorizerConfiguration,
    ProtocolType,
    Gateway,
    GatewayAuthorizer,
    GatewayCredentialProvider,
)
from constructs import Construct


class AgentCoreMCPDemoStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stack_name = "agentcore-mcp-demo"

        # ECR Repository
        ecr_repo = ecr.Repository(
            self,
            "MCPServerRepo",
            repository_name=f"{stack_name}-mcp-server",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        # IAM Role for Runtime
        runtime_role = iam.Role(
            self,
            "RuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
        )

        runtime_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess")
        )

        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )

        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                resources=[ecr_repo.repository_arn],
            )
        )

        # Inbound Cognito User Pool (for Gateway authentication)
        inbound_pool = cognito.UserPool(
            self,
            "InboundPool",
            user_pool_name=f"{stack_name}-inbound-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        inbound_domain = inbound_pool.add_domain(
            "InboundDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{stack_name}-inbound-{self.account}",
            ),
        )

        inbound_client = inbound_pool.add_client(
            "InboundClient",
            user_pool_client_name=f"{stack_name}-inbound-client",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_password=True),
        )

        # Outbound Cognito User Pool (for Runtime M2M authentication)
        outbound_pool = cognito.UserPool(
            self,
            "OutboundPool",
            user_pool_name=f"{stack_name}-outbound-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        outbound_domain = outbound_pool.add_domain(
            "OutboundDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{stack_name}-outbound-{self.account}",
            ),
        )

        resource_server = outbound_pool.add_resource_server(
            "MCPResourceServer",
            identifier="mcp-server",
            scopes=[
                cognito.ResourceServerScope(scope_name="tools.execute", scope_description="Execute tools on MCP server"),
            ],
        )

        m2m_client = outbound_pool.add_client(
            "M2MClient",
            user_pool_client_name=f"{stack_name}-m2m-client",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[cognito.OAuthScope.resource_server(resource_server, cognito.ResourceServerScope(scope_name="tools.execute", scope_description="Execute tools on MCP server"))],
            ),
        )

        # Gateway
        gateway = Gateway(
            self,
            "Gateway",
            gateway_name=f"{stack_name}-gateway",
            authorizer_configuration=GatewayAuthorizer.using_cognito(
                user_pool=inbound_pool,
                allowed_clients=[inbound_client]
            ),
        )

        # MCP Runtime
        mcp_runtime_artifact = AgentRuntimeArtifact.from_asset(
            os.path.join(os.path.dirname(__file__), "docker-image")
        )

        mcp_runtime = Runtime(
            self,
            "MCPRuntime",
            runtime_name=f"{stack_name.replace('-', '_')}_mcp_server",
            execution_role=runtime_role,
            agent_runtime_artifact=mcp_runtime_artifact,
            protocol_configuration=ProtocolType.MCP,
            authorizer_configuration=RuntimeAuthorizerConfiguration.using_cognito(
                outbound_pool, [m2m_client],
            ),
        )

        # OAuth2 Credential Provider
        oauth_provider_name = f"{stack_name}-oauth-provider"
        oauth_provider = cr.AwsCustomResource(
            self,
            "OAuthCredentialProvider",
            install_latest_aws_sdk=True,
            on_create=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agentcore-control",
                action="CreateOauth2CredentialProvider",
                parameters={
                    "name": oauth_provider_name,
                    "credentialProviderVendor": "CustomOauth2",
                    "oauth2ProviderConfigInput": {
                        "customOauth2ProviderConfig": {
                            "oauthDiscovery": {
                                "discoveryUrl": f"https://cognito-idp.{self.region}.amazonaws.com/{outbound_pool.user_pool_id}/.well-known/openid-configuration",
                            },
                            "clientId": m2m_client.user_pool_client_id,
                            "clientSecret": m2m_client.user_pool_client_secret.unsafe_unwrap(),
                        },
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("credentialProviderArn"),
            ),
            on_delete=cr.AwsSdkCall(
                service="@aws-sdk/client-bedrock-agentcore-control",
                action="DeleteOauth2CredentialProvider",
                parameters={
                    "name": oauth_provider_name,
                },
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=[
                        "bedrock-agentcore:CreateTokenVault",
                        "bedrock-agentcore:GetTokenVault",
                        "bedrock-agentcore:CreateOauth2CredentialProvider",
                        "bedrock-agentcore:DeleteOauth2CredentialProvider",
                        "secretsmanager:CreateSecret",
                        "secretsmanager:DeleteSecret",
                    ],
                    resources=["*"],
                ),
            ]),
        )

        provider_arn = oauth_provider.get_response_field("credentialProviderArn")
        secret_arn = oauth_provider.get_response_field("clientSecretArn.secretArn")

        # URL-encode the runtime ARN for the endpoint
        escaped_arn = cdk.Fn.join("%2F", cdk.Fn.split("/",
            cdk.Fn.join("%3A", cdk.Fn.split(":", mcp_runtime.agent_runtime_arn))
        ))
        mcp_runtime_endpoint = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"

        # Gateway Target
        gateway.add_mcp_server_target(
            "MCPTarget",
            gateway_target_name=f"{stack_name}-mcp-target",
            description="MCP Server with M2M OAuth authentication",
            endpoint=mcp_runtime_endpoint,
            credential_provider_configurations=[
                GatewayCredentialProvider.from_oauth_identity_arn(
                    provider_arn=provider_arn,
                    secret_arn=secret_arn,
                    scopes=["mcp-server/tools.execute"],
                ),
            ],
        )

        # Outputs
        cdk.CfnOutput(self, "ECRRepositoryUri", value=ecr_repo.repository_uri)
        cdk.CfnOutput(self, "InboundUserPoolId", value=inbound_pool.user_pool_id)
        cdk.CfnOutput(self, "InboundClientId", value=inbound_client.user_pool_client_id)
        cdk.CfnOutput(self, "OutboundUserPoolId", value=outbound_pool.user_pool_id)
        cdk.CfnOutput(self, "M2MClientId", value=m2m_client.user_pool_client_id)
        cdk.CfnOutput(self, "GatewayId", value=gateway.gateway_id)
        cdk.CfnOutput(self, "GatewayUrl", value=gateway.gateway_url)
        cdk.CfnOutput(self, "RuntimeArn", value=mcp_runtime.agent_runtime_arn)
        cdk.CfnOutput(self, "OAuthProviderArn", value=provider_arn)
        cdk.CfnOutput(self, "InboundTokenEndpoint", value=f"{inbound_domain.base_url()}/oauth2/token")
        cdk.CfnOutput(self, "OutboundTokenEndpoint", value=f"{outbound_domain.base_url()}/oauth2/token")
