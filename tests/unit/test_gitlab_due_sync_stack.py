import aws_cdk as core
import aws_cdk.assertions as assertions

from gitlab_due_sync.gitlab_due_sync_stack import GitlabDueSyncStack

# example tests. To run these tests, uncomment this file along with the example
# resource in gitlab_due_sync/gitlab_due_sync_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = GitlabDueSyncStack(app, "gitlab-due-sync")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
