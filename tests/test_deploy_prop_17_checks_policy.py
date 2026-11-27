"""The Lab, Property 15: the policy grants exactly the right DynamoDB actions."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()

account_ids = st.text(alphabet="0123456789", min_size=12, max_size=12)


# Feature: the-lab, Property 15: The permissions policy grants exactly the right DynamoDB actions on the right resource
# **Validates: Requirements 9.2**
@settings(max_examples=100, deadline=None)
@given(account_ids)
def test_policy_has_exact_dynamodb_statement(account_id) -> None:
    policy = deploy.permissions_policy(account_id)
    statements = policy["Statement"]
    assert len(statements) == 4
    dynamo = [s for s in statements if "dynamodb:Scan" in s["Action"]]
    assert len(dynamo) == 1
    assert dynamo[0]["Effect"] == "Allow"
    assert sorted(dynamo[0]["Action"]) == ["dynamodb:PutItem", "dynamodb:Scan"]
    assert dynamo[0]["Resource"] == (
        f"arn:aws:dynamodb:{deploy.REGION}:{account_id}:table/ghost-credit-checks"
    )
    others = [s for s in statements if s is not dynamo[0]][:2]
    assert others[0]["Action"] == "bedrock:InvokeModel"
    assert others[0]["Resource"] == deploy.BEDROCK_MODEL_ARN
    assert others[1]["Action"] == [
        "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
    ]
