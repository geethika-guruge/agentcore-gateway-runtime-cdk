from aws_cdk import (
    Stack,
    CfnOutput,
    aws_cognito as cognito,
    aws_ecr as ecr,
    aws_iam as iam,
    RemovalPolicy,
)
from constructs import Construct


class BaseInfraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ECR Repository
        self.ecr_repo = ecr.Repository(
            self,
            "MCPServerRepo",
            repository_name=f"{project_name}-mcp-server",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        # Inbound Cognito User Pool
        self.inbound_pool = cognito.UserPool(
            self,
            "InboundPool",
            user_pool_name=f"{project_name}-inbound-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
        )

        inbound_domain = self.inbound_pool.add_domain(
            "InboundDomain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=f"{project_name}-inbound"),
        )

        self.inbound_client = self.inbound_pool.add_client(
            "InboundClient",
            user_pool_client_name=f"{project_name}-inbound-client",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_password=True),
        )

        # Outbound Cognito User Pool
        self.outbound_pool = cognito.UserPool(
            self,
            "OutboundPool",
            user_pool_name=f"{project_name}-outbound-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
        )

        outbound_domain = self.outbound_pool.add_domain(
            "OutboundDomain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=f"{project_name}-outbound"),
        )

        resource_server = self.outbound_pool.add_resource_server(
            "MCPResourceServer",
            identifier="mcp-server",
            scopes=[
                cognito.ResourceServerScope(scope_name="tools.read", scope_description="Read tools from MCP server"),
                cognito.ResourceServerScope(scope_name="tools.write", scope_description="Write tools to MCP server"),
                cognito.ResourceServerScope(scope_name="tools.execute", scope_description="Execute tools on MCP server"),
            ],
        )

        mcp_scope = cognito.OAuthScope.resource_server(
            resource_server, 
            cognito.ResourceServerScope(scope_name="tools.read", scope_description="Read tools from MCP server")
        )

        self.m2m_client = self.outbound_pool.add_client(
            "M2MClient",
            user_pool_client_name=f"{project_name}-m2m-client",
            generate_secret=True,
            auth_flows=cognito.AuthFlow(custom=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[mcp_scope],
            ),
        )

        # IAM Roles
        self.runtime_role = iam.Role(
            self,
            "AgentRuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
            ],
            inline_policies={
                "ECRAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["ecr:GetAuthorizationToken"],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                            resources=[self.ecr_repo.repository_arn],
                        ),
                    ]
                ),
            },
        )

        self.gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
            ],
        )

        # Outputs
        CfnOutput(self, "InboundUserPoolId", value=self.inbound_pool.user_pool_id)
        CfnOutput(self, "InboundClientId", value=self.inbound_client.user_pool_client_id)
        CfnOutput(self, "OutboundUserPoolId", value=self.outbound_pool.user_pool_id)
        CfnOutput(self, "M2MClientId", value=self.m2m_client.user_pool_client_id)
        CfnOutput(self, "ECRRepositoryUri", value=self.ecr_repo.repository_uri)
        CfnOutput(self, "RuntimeRoleArn", value=self.runtime_role.role_arn)
        CfnOutput(self, "GatewayRoleArn", value=self.gateway_role.role_arn)
