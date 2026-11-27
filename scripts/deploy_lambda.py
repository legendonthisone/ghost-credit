"""Deploy Ghost Credit to one AWS Lambda with a Function URL.

Usage (PowerShell, from the repo root):
    python scripts\\deploy_lambda.py --dry-run
    python scripts\\deploy_lambda.py

What it does:
- Reads the secrets from the .env file and puts them ONLY into the Lambda
  environment variables. Values are never printed, logged or written anywhere.
- Builds a zip of src/ghost_credit only (no tests, no .env, no caches).
- Creates or updates: one IAM role, one inline policy, one Lambda function, one
  Function URL (auth NONE) and its two public-invoke permissions.
- --dry-run builds the zip in memory and prints the plan. It makes no AWS call.

The pure helpers below import without boto3. boto3 is imported only inside the
functions that call AWS. The user runs this script. Tests never do.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

FUNCTION_NAME = "ghost-credit"
ROLE_NAME = "ghost-credit-lambda"
POLICY_NAME = "ghost-credit-lambda-policy"
REGION = "us-east-1"
BEDROCK_MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0"
HANDLER = "ghost_credit.lambda_handler.lambda_handler"
RUNTIME = "python3.12"
TIMEOUT_SECONDS = 30
MEMORY_MB = 256
ZIP_ROOT = "ghost_credit"
CHECKS_TABLE_NAME = "ghost-credit-checks"
RESERVED_CONCURRENCY = 5

WHATSAPP_NAMES = (
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_APP_SECRET",
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
)
PAYSTACK_NAME = "PAYSTACK_SECRET_KEY"
LAMBDA_VARIABLE_NAMES = WHATSAPP_NAMES + (
    PAYSTACK_NAME,
    "EXPLAINER",
    "MERCHANT_CATEGORY",
    "PATTERN_NETWORK",
    "CHECKS_TABLE",
)

# The test-key prefix is built from two pieces so the whole prefix is never one
# literal in this file.
_TEST_KEY_PREFIX = "sk_" + "test_"

_EXCLUDED_DIRS = {"tests", "__pycache__", ".hypothesis"}
_PERMISSION_URL_ID = "FunctionURLAllowPublicAccess"
_PERMISSION_INVOKE_ID = "FunctionURLAllowInvokeAction"
_FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


# --- Pure helpers (tested, no AWS) -------------------------------------------


def parse_env_text(text: str) -> dict[str, str]:
    """Parse NAME=value lines into a dict.

    Blank lines and lines starting with # are skipped. Each line splits at the
    first "=". One pair of matching surrounding quotes is removed.
    """
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if name:
            values[name] = value
    return values


def select_lambda_variables(values: dict[str, str]) -> dict[str, str]:
    """Pick only the allowed names for the Lambda.

    PATTERN_NETWORK is always "off". Empty values are left out. MERCHANT_CATEGORY
    defaults to "other", EXPLAINER to "template" and CHECKS_TABLE to the
    Lab's table name.
    """
    selected = {
        name: values[name]
        for name in LAMBDA_VARIABLE_NAMES
        if name != "PATTERN_NETWORK" and values.get(name)
    }
    selected.setdefault("MERCHANT_CATEGORY", "other")
    selected.setdefault("EXPLAINER", "template")
    selected.setdefault("CHECKS_TABLE", CHECKS_TABLE_NAME)
    selected["PATTERN_NETWORK"] = "off"
    return selected


def missing_whatsapp_names(selected: dict[str, str]) -> list[str]:
    """Return the WhatsApp variable names that have no value."""
    return [name for name in WHATSAPP_NAMES if not selected.get(name)]


def is_test_key(value: object) -> bool:
    """True only for a string that starts with the Paystack test-key prefix."""
    return isinstance(value, str) and value.startswith(_TEST_KEY_PREFIX)


def _is_excluded(relative: Path) -> bool:
    """Say whether a path under the package must stay out of the zip."""
    if any(part in _EXCLUDED_DIRS for part in relative.parts[:-1]):
        return True
    name = relative.name
    return name == ".env" or name.startswith(".env.") or name.endswith(".pyc")


def build_zip(src_package_dir: Path) -> bytes:
    """Zip the package folder in memory. Every path starts with ghost_credit/."""
    root = Path(src_package_dir)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if _is_excluded(relative):
                continue
            info = zipfile.ZipInfo(f"{ZIP_ROOT}/{relative.as_posix()}", _FIXED_ZIP_TIME)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return buffer.getvalue()


def trust_policy() -> dict:
    """Return the role trust policy: only the Lambda service may assume it."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }


def checks_table_permissions_statement(account_id: str, region: str) -> dict:
    """Return the statement that lets the function write and read the Lab table only."""
    return {
        "Effect": "Allow",
        "Action": ["dynamodb:PutItem", "dynamodb:Scan"],
        "Resource": f"arn:aws:dynamodb:{region}:{account_id}:table/{CHECKS_TABLE_NAME}",
    }


def lab_url(function_url: str) -> str:
    """Return the Function URL with ``lab`` added as one path segment."""
    return function_url.rstrip("/") + "/lab"


def permissions_policy(account_id: str) -> dict:
    """Return the one inline policy: one Bedrock model, this log group, the Lab table."""
    log_group = f"arn:aws:logs:{REGION}:{account_id}:log-group:/aws/lambda/{FUNCTION_NAME}:*"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": BEDROCK_MODEL_ARN,
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": log_group,
            },
            checks_table_permissions_statement(account_id, REGION),
        ],
    }


def format_plan(selected_names: list[str], zip_files: int, zip_bytes: int) -> str:
    """Return the plan text. It holds names and counts only, never values."""
    lines = [
        "Plan (names only, no values):",
        f"  Region: {REGION}",
        f"  Lambda function: {FUNCTION_NAME} ({RUNTIME}, {MEMORY_MB} MB, {TIMEOUT_SECONDS} s)",
        f"  Handler: {HANDLER}",
        f"  IAM role: {ROLE_NAME}",
        f"  Bedrock model allowed: {BEDROCK_MODEL_ARN}",
        f"  DynamoDB table: {CHECKS_TABLE_NAME} (created if missing, pay per request, TTL on expires_at)",
        f"  Reserved concurrency: {RESERVED_CONCURRENCY} (a refusal prints a warning and the deploy continues)",
        "  Function URL: created or updated at deploy time (auth NONE)",
        f"  Zip: {zip_files} files, {zip_bytes} bytes",
        "  Environment variable names: " + (", ".join(sorted(selected_names)) or "(none)"),
    ]
    return "\n".join(lines)


# --- AWS steps (never run by tests; boto3 imported inside) --------------------


def _error_code(exc: BaseException) -> str:
    """Return the AWS error code of an exception, or "" when it has none."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict) and isinstance(error.get("Code"), str):
            return error["Code"]
    return ""


def _ensure_role(iam: object, account_id: str) -> str:
    """Create or update the role and its inline policy. Return the role ARN."""
    import json

    created = False
    try:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]  # type: ignore[attr-defined]
        iam.update_assume_role_policy(  # type: ignore[attr-defined]
            RoleName=ROLE_NAME, PolicyDocument=json.dumps(trust_policy())
        )
    except Exception as exc:  # noqa: BLE001
        if _error_code(exc) != "NoSuchEntity":
            raise
        role = iam.create_role(  # type: ignore[attr-defined]
            RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust_policy())
        )["Role"]
        created = True
    iam.put_role_policy(  # type: ignore[attr-defined]
        RoleName=ROLE_NAME,
        PolicyName=POLICY_NAME,
        PolicyDocument=json.dumps(permissions_policy(account_id)),
    )
    if created:
        time.sleep(10)  # a new role needs a short time to reach Lambda
    return role["Arn"]


def _function_exists(client: object) -> bool:
    """Say whether the Lambda function already exists."""
    try:
        client.get_function(FunctionName=FUNCTION_NAME)  # type: ignore[attr-defined]
        return True
    except Exception as exc:  # noqa: BLE001
        if _error_code(exc) == "ResourceNotFoundException":
            return False
        raise


def _create_function(client: object, role_arn: str, zip_bytes: bytes, variables: dict) -> None:
    """Create the function, retrying while the new role is still spreading."""
    last: Exception | None = None
    for _ in range(6):
        try:
            client.create_function(  # type: ignore[attr-defined]
                FunctionName=FUNCTION_NAME, Runtime=RUNTIME, Role=role_arn,
                Handler=HANDLER, Code={"ZipFile": zip_bytes},
                Timeout=TIMEOUT_SECONDS, MemorySize=MEMORY_MB,
                Environment={"Variables": variables}, Publish=True,
            )
            return
        except Exception as exc:  # noqa: BLE001
            if _error_code(exc) != "InvalidParameterValueException":
                raise
            last = exc
            time.sleep(5)
    assert last is not None
    raise last


def _update_function(client: object, role_arn: str, zip_bytes: bytes, variables: dict) -> None:
    """Update the code, then the configuration, waiting after each step."""
    waiter = client.get_waiter("function_updated_v2")  # type: ignore[attr-defined]
    client.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)  # type: ignore[attr-defined]
    waiter.wait(FunctionName=FUNCTION_NAME)
    client.update_function_configuration(  # type: ignore[attr-defined]
        FunctionName=FUNCTION_NAME, Role=role_arn, Handler=HANDLER, Runtime=RUNTIME,
        Timeout=TIMEOUT_SECONDS, MemorySize=MEMORY_MB,
        Environment={"Variables": variables},
    )
    waiter.wait(FunctionName=FUNCTION_NAME)


def _ensure_function_url(client: object) -> str:
    """Create or update the Function URL (auth NONE) and return it."""
    try:
        client.get_function_url_config(FunctionName=FUNCTION_NAME)  # type: ignore[attr-defined]
        config = client.update_function_url_config(  # type: ignore[attr-defined]
            FunctionName=FUNCTION_NAME, AuthType="NONE"
        )
    except Exception as exc:  # noqa: BLE001
        if _error_code(exc) != "ResourceNotFoundException":
            raise
        config = client.create_function_url_config(  # type: ignore[attr-defined]
            FunctionName=FUNCTION_NAME, AuthType="NONE"
        )
    return str(config["FunctionUrl"])


def _add_permission(client: object, **kwargs: object) -> None:
    """Add one permission. An existing one counts as success."""
    try:
        client.add_permission(FunctionName=FUNCTION_NAME, Principal="*", **kwargs)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        if _error_code(exc) != "ResourceConflictException":
            raise


def _ensure_checks_table(dynamodb: object) -> None:
    """Create the Lab table if it is missing, then make sure TTL is on.

    Why: The Lab keeps check results for 30 days. DynamoDB deletes expired
    rows itself once TTL is enabled on ``expires_at``. An existing table is
    left as it is.
    """
    try:
        dynamodb.describe_table(TableName=CHECKS_TABLE_NAME)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        if _error_code(exc) != "ResourceNotFoundException":
            raise
        dynamodb.create_table(  # type: ignore[attr-defined]
            TableName=CHECKS_TABLE_NAME,
            AttributeDefinitions=[{"AttributeName": "check_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "check_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.get_waiter("table_exists").wait(TableName=CHECKS_TABLE_NAME)  # type: ignore[attr-defined]
    try:
        dynamodb.update_time_to_live(  # type: ignore[attr-defined]
            TableName=CHECKS_TABLE_NAME,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
        )
    except Exception as exc:  # noqa: BLE001
        if _error_code(exc) != "ValidationException":  # already enabled
            raise


def _set_reserved_concurrency(client: object) -> bool:
    """Cap the function at 5 parallel runs. A refusal only prints a warning.

    Why: new AWS accounts often cannot reserve concurrency. The deploy must
    carry on, but the owner needs to know the cap is not in place.
    """
    try:
        client.put_function_concurrency(  # type: ignore[attr-defined]
            FunctionName=FUNCTION_NAME,
            ReservedConcurrentExecutions=RESERVED_CONCURRENCY,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - any failure must not stop the deploy
        code = _error_code(exc)
        print(
            f"WARNING: reserved concurrency {RESERVED_CONCURRENCY} was NOT set "
            f"({type(exc).__name__} {code}".rstrip() + "). "
            "The deploy continues without that cap."
        )
        return False


def _deploy(zip_bytes: bytes, variables: dict[str, str]) -> str:
    """Create or update every AWS resource. Return the Function URL."""
    import boto3  # imported here so the helpers work without boto3

    account_id = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    _ensure_checks_table(boto3.client("dynamodb", region_name=REGION))
    role_arn = _ensure_role(boto3.client("iam", region_name=REGION), account_id)
    client = boto3.client("lambda", region_name=REGION)
    if _function_exists(client):
        _update_function(client, role_arn, zip_bytes, variables)
    else:
        _create_function(client, role_arn, zip_bytes, variables)
        client.get_waiter("function_active_v2").wait(FunctionName=FUNCTION_NAME)
    _set_reserved_concurrency(client)
    url = _ensure_function_url(client)
    _add_permission(
        client, StatementId=_PERMISSION_URL_ID,
        Action="lambda:InvokeFunctionUrl", FunctionUrlAuthType="NONE",
    )
    _add_permission(
        client, StatementId=_PERMISSION_INVOKE_ID,
        Action="lambda:InvokeFunction", InvokedViaFunctionUrl=True,
    )
    return url


# --- Entry point -------------------------------------------------------------


def _count_zip_files(zip_bytes: bytes) -> int:
    """Return how many files the zip holds."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        return len(archive.namelist())


def main(argv: list[str] | None = None) -> int:
    """Run the deploy or the dry run. Prints names only. Returns an exit code."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Deploy Ghost Credit to AWS Lambda.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, no AWS call")
    parser.add_argument("--env-file", default=str(root / ".env"), help="path to the env file")
    args = parser.parse_args(argv)

    env_path = Path(args.env_file)
    if not env_path.is_file():
        print("Stopped: the env file was not found.")
        return 1
    variables = select_lambda_variables(parse_env_text(env_path.read_text(encoding="utf-8")))

    if not is_test_key(variables.get(PAYSTACK_NAME)):
        print(f"Stopped: {PAYSTACK_NAME} is missing or is not a Paystack test key.")
        return 1
    missing = missing_whatsapp_names(variables)
    if missing and not args.dry_run:
        print("Stopped: these WhatsApp variables are missing: " + ", ".join(missing))
        return 1

    package_dir = root / "src" / ZIP_ROOT
    zip_bytes = build_zip(package_dir)
    print(format_plan(list(variables), _count_zip_files(zip_bytes), len(zip_bytes)))
    if missing:
        print("Missing WhatsApp variables (fix before deploying): " + ", ".join(missing))
    if args.dry_run:
        print("Dry run only. No AWS call was made.")
        return 0

    try:
        url = _deploy(zip_bytes, variables)
    except Exception as exc:  # noqa: BLE001 - print the type and code only, never a value
        code = _error_code(exc)
        print(f"Deploy failed: {type(exc).__name__} {code}".rstrip())
        return 1
    print(f"Deployed function: {FUNCTION_NAME}")
    print("Variables set: " + ", ".join(sorted(variables)))
    print(f"Function URL: {url}")
    print(f"Lab URL: {lab_url(url)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
