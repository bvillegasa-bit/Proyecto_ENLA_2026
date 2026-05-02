# GitHub Secrets Configuration

## Overview

This document describes the required GitHub repository secrets for the ENLA 2026 Callao ML Prediction Pipeline. These secrets enable GitHub Actions workflows to authenticate with Google Cloud Platform, MongoDB Atlas, and SendGrid.

## Required Secrets

Go to your repository > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**

| Secret Name | Description | Example Value | Required For |
|-------------|-------------|---------------|--------------|
| `GCP_PROJECT_ID` | Your GCP project ID | `enla-2026-callao-123456` | All workflows (Terraform, Cloud Functions, dbt, Pipeline) |
| `GCP_SA_KEY` | Service account JSON key | `{ "type": "service_account", "project_id": "...", ... }` | Terraform, Cloud Functions, dbt, Pipeline |
| `MONGODB_URI` | MongoDB Atlas connection string | `mongodb+srv://user:pass@cluster.mongodb.net/` | CI, Cloud Functions, Pipeline |
| `SENDGRID_API_KEY` | SendGrid API key for email alerts | `SG.xxxxx.yyyyy` | CI, Cloud Functions, Pipeline |

## How to Get GCP Service Account Key

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project: `enla-2026-callao-xxxxx`
3. Navigate to **IAM & Admin** > **Service Accounts**
4. Look for or create the service account: `enla-pipeline-sa@<project-id>.iam.gserviceaccount.com`
5. Click on the service account email
6. Go to **Keys** tab
7. Click **Add Key** > **Create new key**
8. Select **JSON** as key type
9. Click **Create** - the JSON file will download automatically
10. Open the downloaded JSON file
11. Copy the **entire content** (including braces `{}`)
12. Paste this as the `GCP_SA_KEY` secret in GitHub

### Required IAM Roles for Service Account

Ensure the service account has these roles:
- `BigQuery Admin` - For dbt and ML model operations
- `Cloud Functions Developer` - For deploying Cloud Functions
- `Service Account User` - For running functions
- `Storage Admin` - For GCS buckets
- `Secret Manager Admin` - For managing secrets
- `Compute Network Admin` - For VPC/VPN if needed
- `Terraform Admin` - If using Terraform with this SA

## How to Get MongoDB Atlas Connection String

1. Go to [MongoDB Atlas](https://cloud.mongodb.com)
2. Log in to your Atlas account
3. Select your cluster: `ENLA-2026-Callao`
4. Click **Connect** button
5. Choose **Connect your application**
6. Select **Python** as driver and version **3.6 or later**
7. Copy the connection string (looks like `mongodb+srv://<username>:<password>@cluster0.mongodb.net/...`)
8. Replace `<username>` and `<password>` with your actual database user credentials
9. Paste this as the `MONGODB_URI` secret

### Creating MongoDB Atlas Database User

If you don't have a database user:
1. In Atlas, go to **Database Access** under Security
2. Click **Add New Database User**
3. Choose **Password** authentication
4. Set username and password
5. Assign **Read and write to any database** privileges
6. Click **Add User**

## How to Get SendGrid API Key

1. Go to [SendGrid](https://app.sendgrid.com)
2. Log in to your SendGrid account
3. Navigate to **Settings** > **API Keys**
4. Click **Create API Key**
5. Name it: `enla-2026-callao-pipeline`
6. Select **Restricted Access**
7. Enable these permissions:
   - **Mail Send**: Full Access
   - **Sender Authentication**: Read Access (optional)
8. Click **Create & View**
9. **Important**: Copy the API key immediately - you won't see it again!
10. Paste this as the `SENDGRID_API_KEY` secret

### Verifying Sender Identity

Before using SendGrid:
1. Go to **Sender Authentication** in SendGrid
2. Verify a sender identity (email or domain)
3. Use this verified email as the `from_email` in the alerting configuration

## Verifying Secrets Configuration

After adding all secrets, you can verify them by:

1. Go to **Actions** tab in your GitHub repository
2. Select any workflow (e.g., "CI Pipeline")
3. Click **Run workflow**
4. Check if the workflow runs without authentication errors

## Troubleshooting

### Common Issues

**Error: `Could not load default credentials`**
- Cause: `GCP_SA_KEY` is invalid or missing
- Solution: Re-download the service account key and ensure it's valid JSON

**Error: `MongoDB connection timeout`**
- Cause: `MONGODB_URI` is incorrect or IP not whitelisted
- Solution: Check URI format and add `0.0.0.0/0` to IP Access List in Atlas (or specific GitHub Actions IPs)

**Error: `SendGrid API key invalid`**
- Cause: `SENDGRID_API_KEY` is expired or incorrect
- Solution: Generate a new API key in SendGrid

**Error: `Permission denied` on GCP resources**
- Cause: Service account missing IAM roles
- Solution: Add required roles to the service account

## Security Best Practices

1. **Never commit secrets to code** - Always use GitHub Secrets
2. **Rotate keys regularly** - Rotate service account keys and API keys periodically
3. **Use least privilege** - Only grant necessary IAM roles to the service account
4. **Audit secret access** - Monitor usage in GCP Audit Logs and SendGrid Activity Feed
5. **Limit secret visibility** - Only repository admins should manage secrets

## Additional Resources

- [GitHub Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [GCP Service Accounts](https://cloud.google.com/iam/docs/service-accounts)
- [MongoDB Atlas Connection Strings](https://www.mongodb.com/docs/atlas/connection-strings/)
- [SendGrid API Keys](https://docs.sendgrid.com/ui/account-and-settings/api-keys)

## Next Steps

After configuring secrets:
1. Run the CI pipeline to verify basic setup
2. Run Terraform workflow to provision infrastructure
3. Deploy Cloud Functions
4. Run the full pipeline manually to test end-to-end
