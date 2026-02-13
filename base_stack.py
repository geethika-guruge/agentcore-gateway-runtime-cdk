from aws_cdk import Stack, RemovalPolicy, CfnOutput
from aws_cdk import aws_ecr as ecr
from constructs import Construct


class BaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ECR Repository
        self.ecr_repository = ecr.Repository(
            self,
            "MCPServerRepository",
            repository_name="mcp-server-runtime",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        CfnOutput(self, "ECRRepositoryUri", value=self.ecr_repository.repository_uri)
