from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
    CustomResource,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_bedrockagentcore as agentcore,
    aws_lambda as lambda_,
    custom_resources as cr,
)
from constructs import Construct
import random
import string


class M2MAuthGatewayStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "m2m-auth-demo"
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # Cognito Inbound Pool (User → Gateway)
        inbound_pool = cognito.UserPool(
            self,
            "InboundPool",
            user_pool_name=f"{project_name}-inbound-pool",
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            mfa=cognito.Mfa.OFF,
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
        )

        inbound_domain = inbound_pool.add_domain(
            "InboundDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{project_name}-inbound-{suffix}"
            ),
        )

        inbound_client = inbound_pool.add_client(
            "InboundClient",
            user_pool_client_name=f"{project_name}-inbound-client",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True, admin_user_password=True, custom=False, user_srp=False
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=["https://localhost/callback"],
                logout_urls=["https://localhost/logout"],
            ),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
        )

        # Cognito Outbound Pool (Gateway → MCP Server M2M)
        outbound_pool = cognito.UserPool(
            self,
            "OutboundPool",
            user_pool_name=f"{project_name}-outbound-pool",
            password_policy=cognito.PasswordPolicy(min_length=8),
            self_sign_up_enabled=False,
        )

        outbound_domain = outbound_pool.add_domain(
            "OutboundDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{project_name}-outbound-{suffix}"
            ),
        )

        # Resource Server with scopes
        resource_server_scopes = [
            cognito.ResourceServerScope(
                scope_name="tools.read", scope_description="Read access to MCP tools"
            ),
            cognito.ResourceServerScope(
                scope_name="tools.write", scope_description="Write access to MCP tools"
            ),
            cognito.ResourceServerScope(
                scope_name="tools.execute", scope_description="Execute MCP tools"
            ),
        ]

        resource_server = outbound_pool.add_resource_server(
            "MCPResourceServer",
            identifier="mcp-server",
            user_pool_resource_server_name="MCP Server Resource",
            scopes=resource_server_scopes,
        )

        # M2M Client (client_credentials)
        m2m_client = outbound_pool.add_client(
            "M2MClient",
            user_pool_client_name=f"{project_name}-m2m-client",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(resource_server, scope)
                    for scope in resource_server_scopes
                ],
            ),
            access_token_validity=Duration.hours(1),
        )

        # ECR Repository
        ecr_repo = ecr.Repository(
            self,
            "MCPServerRepo",
            repository_name=f"{project_name}-mcp-server",
            image_tag_mutability=ecr.TagMutability.MUTABLE,
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[
                ecr.LifecycleRule(max_image_count=5, rule_priority=1, tag_status=ecr.TagStatus.ANY)
            ],
            image_scan_on_push=True,
        )

        # Agent Runtime IAM Role
        runtime_role = iam.Role(
            self,
            "AgentRuntimeRole",
            role_name=f"{project_name}-agent-runtime-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "ECRAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"]),
                        iam.PolicyStatement(
                            actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                            resources=[ecr_repo.repository_arn],
                        ),
                    ]
                ),
                "CloudWatchLogs": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/*"],
                        )
                    ]
                ),
            },
        )

        # Gateway IAM Role
        gateway_role = iam.Role(
            self,
            "GatewayRole",
            role_name=f"{project_name}-gateway-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "GatewayBasic": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(actions=["bedrock-agentcore:InvokeGateway"], resources=["*"]),
                        iam.PolicyStatement(
                            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/*"],
                        ),
                    ]
                ),
                "GatewayIdentity": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["bedrock-agentcore:GetWorkloadAccessToken"],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default",
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/workload-identity/{project_name}-*",
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["bedrock-agentcore:GetResourceOauth2Token"],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default",
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/workload-identity/*",
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default",
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default/oauth2credentialprovider/*",
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["secretsmanager:GetSecretValue"],
                            resources=[f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:bedrock-agentcore*"],
                        ),
                    ]
                ),
            },
        )

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
                "ClientId": m2m_client.user_pool_client_id,
                "ClientSecret": m2m_client.user_pool_client_secret.unsafe_unwrap(),
                "DiscoveryUrl": f"https://cognito-idp.{self.region}.amazonaws.com/{outbound_pool.user_pool_id}/.well-known/openid-configuration",
            },
        )

        oauth_provider_arn = oauth_provider.get_att_string("CredentialProviderArn")

        # Workload Identity - Commented out as it's not currently used
        # workload_identity = agentcore.CfnWorkloadIdentity(
        #     self,
        #     "WorkloadIdentity",
        #     name=f"{project_name}-gateway-identity",
        #     allowed_resource_oauth2_return_urls=["https://localhost/callback", "https://localhost:3000/callback"],
        # )

        # Agent Runtime - Temporarily commented until ECR image is confirmed
        # agent_runtime = agentcore.CfnRuntime(
        #     self,
        #     "AgentRuntime",
        #     agent_runtime_name=project_name.replace("-", "_") + "_mcp_server",
        #     description="MCP Server with OAuth M2M authentication",
        #     role_arn=runtime_role.role_arn,
        #     agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
        #         container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
        #             container_uri=f"{ecr_repo.repository_uri}:latest"
        #         )
        #     ),
        #     network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
        #     protocol_configuration="MCP",
        #     authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
        #         custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
        #             discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{outbound_pool.user_pool_id}/.well-known/openid-configuration",
        #             allowed_clients=[m2m_client.user_pool_client_id],
        #         )
        #     ),
        #     environment_variables={"LOG_LEVEL": "INFO", "ENVIRONMENT": "dev"},
        # )

        # Gateway - Temporarily commented to isolate Runtime deployment
        # gateway = agentcore.CfnGateway(
        #     self,
        #     "Gateway",
        #     name=f"{project_name}-gateway",
        #     role_arn=gateway_role.role_arn,
        #     protocol_type="MCP",
        #     authorizer_type="CUSTOM_JWT",
        #     authorizer_configuration=agentcore.CfnGateway.AuthorizerConfigurationProperty(
        #         custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
        #             discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{inbound_pool.user_pool_id}/.well-known/openid-configuration",
        #             allowed_clients=[inbound_client.user_pool_client_id],
        #         )
        #     ),
        #     protocol_configuration=agentcore.CfnGateway.GatewayProtocolConfigurationProperty(
        #         mcp=agentcore.CfnGateway.MCPGatewayConfigurationProperty(
        #             instructions="M2M OAuth authenticated MCP Gateway",
        #             search_type="SEMANTIC",
        #             supported_versions=["2025-03-26"],
        #         )
        #     ),
        #     exception_level="DEBUG",
        #     description="AgentCore Gateway with M2M OAuth authentication",
        # )

        # Gateway Target - Temporarily commented to isolate Runtime deployment
        # gateway_target = agentcore.CfnGatewayTarget(
        #     self,
        #     "GatewayTarget",
        #     name=f"{project_name}-mcp-target",
        #     gateway_identifier=gateway.ref,
        #     description="MCP Server target with OAuth M2M authentication",
        #     credential_provider_configurations=[
        #         agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
        #             credential_provider_type="OAuth",
        #             credential_provider=agentcore.CfnGatewayTarget.CredentialProviderProperty(
        #                 oauth_credential_provider=agentcore.CfnGatewayTarget.OAuthCredentialProviderProperty(
        #                     provider_arn=oauth_provider_arn,
        #                     scopes=["mcp-server/tools.read", "mcp-server/tools.write", "mcp-server/tools.execute"],
        #                 )
        #             ),
        #         )
        #     ],
        #     target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
        #         mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
        #             mcp_server=agentcore.CfnGatewayTarget.McpServerTargetConfigurationProperty(
        #                 endpoint=agent_runtime.get_att("AgentRuntimeInvocationUrl").to_string()
        #             )
        #         )
        #     ),
        # )
        # gateway_target.node.add_dependency(oauth_provider)
        # gateway_target.node.add_dependency(agent_runtime)

        # Outputs
        CfnOutput(self, "InboundUserPoolId", value=inbound_pool.user_pool_id)
        CfnOutput(self, "InboundClientId", value=inbound_client.user_pool_client_id)
        CfnOutput(self, "OutboundUserPoolId", value=outbound_pool.user_pool_id)
        CfnOutput(self, "M2MClientId", value=m2m_client.user_pool_client_id)
        CfnOutput(self, "ECRRepositoryUri", value=ecr_repo.repository_uri)
        # CfnOutput(self, "GatewayId", value=gateway.ref)
        # CfnOutput(self, "RuntimeArn", value=agent_runtime.ref)
