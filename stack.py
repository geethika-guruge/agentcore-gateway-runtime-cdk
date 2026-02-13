import os
import json
import aws_cdk as cdk
from aws_cdk import (
    aws_iam as iam,
    aws_cognito as cognito,
    aws_ecr as ecr,
    aws_bedrockagentcore as bedrockagentcore,
    custom_resources as cr,
)
from constructs import Construct


class AgentCoreMCPDemoL1Stack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, ecr_repository: ecr.Repository, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stack_name = "agentcore-mcp-demo-l1"

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
                resources=[ecr_repository.repository_arn],
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

        # Gateway (L1)
        gateway = bedrockagentcore.CfnGateway(
            self,
            "Gateway",
            name=f"{stack_name}-gateway",
            authorizer_type="CUSTOM_JWT",
            protocol_type="MCP",
            role_arn=runtime_role.role_arn,
            authorizer_configuration=bedrockagentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=bedrockagentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{inbound_pool.user_pool_id}/.well-known/openid-configuration",
                    allowed_clients=[inbound_client.user_pool_client_id],
                )
            ),
            protocol_configuration=bedrockagentcore.CfnGateway.GatewayProtocolConfigurationProperty(
                mcp=bedrockagentcore.CfnGateway.MCPGatewayConfigurationProperty(
                    supported_versions=["2025-03-26"]
                )
            ),
        )

        # Build and push Docker image using custom resource
        docker_build = cr.AwsCustomResource(
            self,
            "DockerBuild",
            install_latest_aws_sdk=False,
            on_create=cr.AwsSdkCall(
                service="ecr",
                action="getAuthorizationToken",
                physical_resource_id=cr.PhysicalResourceId.of("docker-build-trigger"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["ecr:GetAuthorizationToken"],
                    resources=["*"],
                ),
            ]),
        )

        # MCP Runtime (L1)
        mcp_runtime = bedrockagentcore.CfnRuntime(
            self,
            "MCPRuntime",
            agent_runtime_name=f"{stack_name.replace('-', '_')}_mcp_server",
            role_arn=runtime_role.role_arn,
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=f"{ecr_repository.repository_uri}:latest",
                )
            ),
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC",
            ),
        )
        mcp_runtime.node.add_dependency(docker_build)

        # OAuth2 Credential Provider - DISABLED FOR NOW
        # oauth_provider_name = f"{stack_name}-oauth-provider"
        # oauth_provider = cr.AwsCustomResource(...)

        # URL-encode the runtime ARN for the endpoint
        escaped_arn = cdk.Fn.join("%2F", cdk.Fn.split("/",
            cdk.Fn.join("%3A", cdk.Fn.split(":", mcp_runtime.attr_agent_runtime_arn))
        ))
        mcp_runtime_endpoint = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"

        # Gateway Target (L1) - COMMENTED OUT - Connection issues with L1 constructs
        # gateway_target = bedrockagentcore.CfnGatewayTarget(
        #     self,
        #     "MCPTarget",
        #     name=f"{stack_name}-mcp-target",
        #     gateway_identifier=gateway.attr_gateway_identifier,
        #     description="MCP Server without authentication",
        #     target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
        #         mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
        #             mcp_server=bedrockagentcore.CfnGatewayTarget.McpServerTargetConfigurationProperty(
        #                 endpoint=mcp_runtime_endpoint,
        #             )
        #         )
        #     ),
        # )

        # Outputs
        cdk.CfnOutput(self, "ECRRepositoryUri", value=ecr_repository.repository_uri)
        cdk.CfnOutput(self, "InboundUserPoolId", value=inbound_pool.user_pool_id)
        cdk.CfnOutput(self, "InboundClientId", value=inbound_client.user_pool_client_id)
        cdk.CfnOutput(self, "OutboundUserPoolId", value=outbound_pool.user_pool_id)
        cdk.CfnOutput(self, "M2MClientId", value=m2m_client.user_pool_client_id)
        cdk.CfnOutput(self, "GatewayId", value=gateway.attr_gateway_identifier)
        cdk.CfnOutput(self, "GatewayUrl", value=gateway.attr_gateway_url)
        cdk.CfnOutput(self, "RuntimeArn", value=mcp_runtime.attr_agent_runtime_arn)
        # cdk.CfnOutput(self, "OAuthProviderArn", value=provider_arn)  # DISABLED
        cdk.CfnOutput(self, "InboundTokenEndpoint", value=f"{inbound_domain.base_url()}/oauth2/token")
        cdk.CfnOutput(self, "OutboundTokenEndpoint", value=f"{outbound_domain.base_url()}/oauth2/token")
