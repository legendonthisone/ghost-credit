# Deploy Ghost Credit to AWS Lambda

One Lambda function called `ghost-credit` (Python 3.12, 256 MB, 30 seconds) behind a Function URL. Meta's WhatsApp Cloud API calls that URL.

**Before you start**

- Deploying uses AWS. It costs money or free-tier usage only after Ayobami approves it.
- You run the deploy script yourself. Nobody else should run it for you.
- Lambda already ships `boto3`, so no layer is needed. You only install `boto3` on your own computer to run the script.
- The "seen message" memory (dedupe) lasts only as long as one Lambda container. A durable store for it is not included and needs approval first.
- Used payment references are kept in a DynamoDB table (`ghost-credit-used-refs`) so one real payment cannot confirm two checks, even after a restart. Only a hash of each reference is kept, for 30 days. See step 3.
- Secrets go only into the Lambda environment variables, read from your `.env` file at deploy time. The script prints variable names, never values.

## 1. Prerequisites

1. Install the AWS CLI and sign in with credentials that may create IAM roles and Lambda functions. The same identity also needs DynamoDB permissions to create tables (`dynamodb:CreateTable`), check them (`dynamodb:DescribeTable`) and turn on expiry (`dynamodb:UpdateTimeToLive`).:

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
   | `SCREENSHOT_READER` | `fake` (free, the default) or `vision`. `vision` reads screenshots with Amazon Nova Lite, which costs a small amount per image. Leave empty to use `fake`. |
   | `MERCHANT_CATEGORY` | For example `spa`. Leave empty to use `other`. |
   | `LEDGER_HMAC_KEY` | A long random value you invent (at least 32 random characters). See the notes below. |
   | `USED_REFS_TABLE` | Leave empty to use `ghost-credit-used-refs`. |
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

It also creates two DynamoDB tables if they are missing (pay per request, expiry switched on for `expires_at`):

- `ghost-credit-checks` holds the anonymised results shown on The Lab page.
- `ghost-credit-used-refs` holds hashed payment references, so a reused receipt is caught.

The role may only do these things in `us-east-1`:

- Call the `amazon.nova-micro-v1:0` model (reply wording) and the `amazon.nova-lite-v1:0` model (screenshot reading), and write its own logs.
- `PutItem` and `Scan` on `ghost-credit-checks`.
- `GetItem` and `PutItem` on `ghost-credit-used-refs`. Nothing else.

**About `LEDGER_HMAC_KEY`**

- Choose a long random value and keep it only in `.env`.
- Never change it after go-live. A new key makes every old receipt look new, so the reused-receipt check forgets the past 30 days.
- Never share it or paste it into chat, tickets or screenshots. If it is empty, the function falls back to a memory-only ledger that is lost whenever the container restarts.

**About reserved concurrency**

The script limits the function to 5 runs at the same time. Some new AWS accounts refuse this. If so, the script prints a `WARNING` line and the deploy carries on without the limit. Ask AWS Support to raise the account limit, then run the script again.

## 4. Register the webhook in Meta

1. Open your app in the Meta developer dashboard, then **WhatsApp**, then **Configuration**.
2. Under **Webhook**, click **Edit**.
3. Callback URL: paste the Function URL.
4. Verify token: paste the same phrase you put in `WHATSAPP_VERIFY_TOKEN`.
5. Click **Verify and save**. Meta sends a GET call and the function answers it.

## 5. Subscribe to messages

In the same **Configuration** page, under **Webhook fields**, click **Manage** and subscribe to `messages`.

## 6. Test

The Lab page is the Function URL with `/lab` added at the end. The script prints it as `Lab URL` when the deploy finishes. Open it in a browser to see recent anonymised checks.

1. From a phone that is on your WhatsApp test number list, send the test number a pasted bank SMS (fake text is fine).
2. You should get a short verdict reply on WhatsApp.
3. If nothing arrives, read the logs (they hold event names only):

   ```powershell
   aws logs tail /aws/lambda/ghost-credit --since 10m --region us-east-1
   ```

With `SCREENSHOT_READER=vision`, a screenshot you send is read in memory and checked like an SMS. With the default `fake`, or if the screenshot cannot be read, the reply asks you to paste the SMS text.

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
aws dynamodb delete-table --table-name ghost-credit-checks --region us-east-1
aws dynamodb delete-table --table-name ghost-credit-used-refs --region us-east-1
```

Then remove the webhook from the Meta dashboard.
