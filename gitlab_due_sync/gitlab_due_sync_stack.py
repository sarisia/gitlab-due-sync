from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_python_alpha as lambda_python,
)
from constructs import Construct

class GitlabDueSyncStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # read config json
        config_json_str = ""
        with open("client_secret.json") as f:
            config_json_str = f.read()

        # db
        table = dynamodb.Table(
            self,
            "Table",
            partition_key=dynamodb.Attribute(
                name="username",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        # webhook function
        webhook_func = lambda_python.PythonFunction(
            self,
            "WebhookFunction",
            entry="./src",
            index="handler_main.py",
            handler="handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            architecture=lambda_.Architecture.ARM_64,
            environment={
                "DUESYNC_GOOGLE_AUTH_TABLE_NAME": table.table_name
            }
        )
        webhook_func_url = webhook_func.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE
        )
        table.grant_read_data(webhook_func)
        # webhook_func.add_environment("TESTENV", webhook_func_url.url)

        # auth function
        auth_func = lambda_python.PythonFunction(
            self,
            "AuthFunction",
            entry="./src",
            index="handler_auth.py",
            handler="handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            architecture=lambda_.Architecture.ARM_64,
            environment={
                "DUESYNC_GOOGLE_AUTH_TABLE_NAME": table.table_name,
                "DUESYNC_GOOGLE_AUTH_CLIENT_CONFIG_JSON": config_json_str,
                "DUESYNC_WEBHOOK_BASE_URL": webhook_func_url.url
            }
        )
        auth_func.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE
        )
        table.grant_read_write_data(auth_func)
