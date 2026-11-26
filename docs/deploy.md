# Deploy Ghost Credit to AWS Lambda

One Lambda function called `ghost-credit` (Python 3.12, 256 MB, 30 seconds) behind a Function URL. Meta's WhatsApp Cloud API calls that URL.

**Before you start**

- Deploying uses AWS. It costs money or free-tier usage only after Ayobami approves it.
- You run the deploy script yourself. Nobody else should run it for you.
- Lambda already ships `boto3`, so no layer is needed. You only install `boto3` on your own computer to run the script.
- The "seen message" memory (dedupe) and any in-memory used-payments ledger last only as long as one Lambda container. A durable store (for example a database table) is not included and needs approval first.
- Secrets go only into the Lambda environment variables, read from your `.env` file at deploy time. The script prints variable names, never values.

## 1. Prerequisites

1. Install the AWS CLI and sign in with credentials that may create IAM roles and Lambda functions:

   ```powershell
   aws configure
   aws sts get-caller-identity
   ```

2. Install `boto3` on your computer (a recent version, so the Function URL permission option is supported):

   ```powershell
   python -m pip install --upgrade boto3
   ```

3. Copy the example file and fill in `.env` (test keys only, never commit it):

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Fill in these names:

   | Name | What it is |
   |---|---|
   | `WHATSAPP_VERIFY_TOKEN` | A long random phrase you invent. You paste the same phrase into Meta. |
   | `WHATSAPP_APP_SECRET` | The app secret from the Meta app settings. |
   | `WHATSAPP_TOKEN` | The WhatsApp access token. |
   | `WHATSAPP_PHONE_NUMBER_ID` | The phone number id from the WhatsApp setup page. |
   | `PAYSTACK_SECRET_KEY` | The Paystack test secret key. The script refuses anything that is not a test key. |
   | `EXPLAINER` | `template` (free). Leave empty to use `template`. |
   | `MERCHANT_CATEGORY` | For example `spa`. Leave empty to use `other`. |
   | `PATTERN_NETWORK` | Leave empty. The script always sets it to `off`. |

## 2. Dry run (no AWS call)

```powershell
python scripts\deploy_lambda.py --dry-run
```

It builds the zip in memory and prints the plan: resource names, file count, size and variable names. It lists any missing WhatsApp names. Fix them in `.env` and run it again until none are missing.

## 3. Deploy

```powershell
python scripts\deploy_lambda.py
```

It creates or updates the IAM role `ghost-credit-lambda`, the function, the Function URL and the two public-invoke permissions. At the end it prints the variable names and the Function URL. Copy the Function URL.

The role may only call the `amazon.nova-micro-v1:0` model in `us-east-1` and write its own logs.

## 4. Register the webhook in Meta

1. Open your app in the Meta developer dashboard, then **WhatsApp**, then **Configuration**.
2. Under **Webhook**, click **Edit**.
3. Callback URL: paste the Function URL.
4. Verify token: paste the same phrase you put in `WHATSAPP_VERIFY_TOKEN`.
5. Click **Verify and save**. Meta sends a GET call and the function answers it.

## 5. Subscribe to messages

In the same **Configuration** page, under **Webhook fields**, click **Manage** and subscribe to `messages`.

## 6. Test

1. From a phone that is on your WhatsApp test number list, send the test number a pasted bank SMS (fake text is fine).
2. You should get a short verdict reply on WhatsApp.
3. If nothing arrives, read the logs (they hold event names only):

   ```powershell
   aws logs tail /aws/lambda/ghost-credit --since 10m --region us-east-1
   ```

Images are not read yet. If you send a screenshot, the reply asks you to paste the SMS text.

## 7. Update

Change `.env` or the code, then run the script again. It updates the existing resources and creates no duplicates.

```powershell
python scripts\deploy_lambda.py --dry-run
python scripts\deploy_lambda.py
```

## 8. Delete everything

Run these in order. The first command removes the public URL.

```powershell
aws lambda delete-function-url-config --function-name ghost-credit --region us-east-1
aws lambda delete-function --function-name ghost-credit --region us-east-1
aws iam delete-role-policy --role-name ghost-credit-lambda --policy-name ghost-credit-lambda-policy
aws iam delete-role --role-name ghost-credit-lambda
aws logs delete-log-group --log-group-name /aws/lambda/ghost-credit --region us-east-1
```

Then remove the webhook from the Meta dashboard.
