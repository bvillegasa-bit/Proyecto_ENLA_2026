# ENLA 2026 Callao - Operational Runbook

> **Sprint 6: Infrastructure + Visualization**
> Last Updated: 2026-05-01

## Table of Contents

1. [Overview](#overview)
2. [Infrastructure Deployment](#infrastructure-deployment)
3. [Cloud Function Deployment](#cloud-function-deployment)
4. [dbt Transformation Deployment](#dbt-transformation-deployment)
5. [Pipeline Operations](#pipeline-operations)
6. [Dashboard Management](#dashboard-management)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Troubleshooting](#troubleshooting)
9. [Incident Response](#incident-response)

---

## Overview

The ENLA 2026 Callao pipeline predicts academic success for educational institutions in Callao, Peru across 4 areas:
- Comunicación
- Matemática
- CCSS (Ciencias Sociales)
- CyT (Ciencia y Tecnología)

### Pipeline Flow

```
Excel File → MongoDB → BigQuery → Features → ML Models → Predictions → Alerts → Dashboards
   ↓            ↓           ↓          ↓          ↓           ↓          ↓
Sprint 1    Sprint 2   Sprint 2   Sprint 3   Sprint 4    Sprint 5   Sprint 6
```

### Key Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| BigQuery Dataset | `BI_ENLA` (US) | Data warehouse |
| GCS Bucket | `enla-raw-data-{project_id}` | Raw Excel file storage |
| Pub/Sub Topic | `enla-raw-data-ready` | Pipeline trigger |
| Cloud Function | `enla-pipeline-orchestrator` | Pipeline orchestration |
| Looker Studio | 5 dashboards | Data visualization |

---

## Infrastructure Deployment

### Prerequisites

```bash
# Required tools
terraform --version    # >= 1.3.0
gcloud --version       # Google Cloud SDK
```

### Authentication

```bash
# Authenticate with GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Deploy Infrastructure

```bash
cd terraform/

# Initialize Terraform
terraform init

# Review the execution plan
terraform plan \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="region=us" \
  -var="environment=prod" \
  -var="mongodb_uri=YOUR_MONGODB_URI" \
  -var="sendgrid_api_key=YOUR_SENDGRID_KEY" \
  -var="alert_emails=[\"admin@example.com\"]"

# Apply the configuration
terraform apply \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="region=us" \
  -var="environment=prod" \
  -var="mongodb_uri=YOUR_MONGODB_URI" \
  -var="sendgrid_api_key=YOUR_SENDGRID_KEY" \
  -var="alert_emails=[\"admin@example.com\"]"
```

### Verify Deployment

```bash
# Check outputs
terraform output

# Verify BigQuery dataset
bq ls --dataset_id BI_ENLA

# Verify GCS bucket
gsutil ls gs://enla-raw-data-YOUR_PROJECT_ID/

# Verify Pub/Sub topic
gcloud pubsub topics list | grep enla-raw-data-ready
```

---

## Cloud Function Deployment

### Deploy via gcloud (Recommended)

```bash
# Deploy the Cloud Function
gcloud functions deploy enla-pipeline-orchestrator \
  --runtime python311 \
  --entry-point enla_pipeline_orchestrator \
  --trigger-topic enla-raw-data-ready \
  --timeout 540s \
  --memory 512MB \
  --set-env-vars GCP_PROJECT=YOUR_PROJECT_ID \
  --set-secrets MONGODB_URI=MONGODB_URI:latest \
  --set-secrets SENDGRID_API_KEY=SENDGRID_API_KEY:latest \
  --source gcp/functions/enla_orchestrator/
```

### Deploy via Terraform (CI/CD)

```bash
# After terraform apply, upload function source to GCS
cd gcp/functions/enla_orchestrator/
zip -r enla_orchestrator.zip .
gsutil cp enla_orchestrator.zip gs://enla-raw-data-YOUR_PROJECT_ID/functions/
```

### Test the Cloud Function

```bash
# Health check
curl https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/enla-pipeline-orchestrator/health

# Trigger pipeline manually (via Pub/Sub)
gcloud pubsub topics publish enla-raw-data-ready \
  --message '{"source":"manual","model_version":"v1"}'
```

---

## dbt Transformation Deployment

### Prerequisites

```bash
# Install dbt-bigquery
pip install dbt-bigquery==1.5.0

# Verify installation
dbt --version
```

### Configure dbt Profile

Create `~/.dbt/profiles.yml`:

```yaml
enla_callao:
  target: prod
  outputs:
    prod:
      type: bigquery
      method: oauth
      project: YOUR_PROJECT_ID
      dataset: BI_ENLA
      threads: 4
      timeout_seconds: 300
      location: US
```

### Run dbt Models

```bash
cd dbt/

# Install dependencies (if any)
dbt deps

# Validate configuration
dbt debug

# Run all models
dbt run

# Run specific models
dbt run --models v_callao_comunicacion_2026

# Test models
dbt test

# Generate documentation
dbt docs generate
dbt docs serve
```

### Seed Data (if applicable)

```bash
# Load seed data (normalization params, etc.)
dbt seed
```

---

## Pipeline Operations

### Manual Pipeline Execution

```bash
# Run full pipeline manually using Python scripts
cd /path/to/enla-2026-callao/

# 1. Ingestion (Excel → MongoDB)
python -m src.ingestion.ingest_enla

# 2. ETL (MongoDB → BigQuery)
python -m src.etl.transform

# 3. Feature Engineering
python -m src.features.engineer

# 4. Model Training & Prediction
python -m src.models.trainer
python -m src.models.predictor

# 5. Send Alerts
python -m src.alerting.email_alert
```

### Check Model Metrics

```bash
# View model performance metrics
bq query --use_legacy_sql=false "
SELECT
  area,
  model_version,
  accuracy,
  precision_score,
  recall_score,
  f1_score,
  training_ts
FROM \`YOUR_PROJECT_ID.BI_ENLA.model_metrics\`
ORDER BY training_ts DESC
LIMIT 20
"
```

### Upload New Excel Data

```bash
# Upload Excel file to GCS (triggers pipeline via Pub/Sub)
gsutil cp data/raw/enla_2026_data.xlsx \
  gs://enla-raw-data-YOUR_PROJECT_ID/input/

# Or trigger manually
gcloud pubsub topics publish enla-raw-data-ready \
  --message '{"gcs_file_path":"gs://enla-raw-data-YOUR_PROJECT_ID/input/enla_2026_data.xlsx"}'
```

---

## Dashboard Management

### Looker Studio Dashboard URLs

After creating dashboards, document URLs here:

| Dashboard | URL | Refresh Schedule |
|-----------|-----|------------------|
| Comunicación | TBD | Daily 03:00 UTC |
| Matemática | TBD | Daily 03:00 UTC |
| CCSS | TBD | Daily 03:00 UTC |
| CyT | TBD | Daily 03:00 UTC |
| Executive Summary | TBD | Daily 03:00 UTC |

### Create Dashboards

1. Go to [Looker Studio](https://lookerstudio.google.com/)
2. Create new report
3. Select BigQuery as data source
4. Navigate to `YOUR_PROJECT_ID.BI_ENLA.v_callao_comunicacion_2026`
5. Follow specs in `docs/DASHBOARD_SPEC.md`

### Configure Scheduled Refresh

In BigQuery, create scheduled queries to refresh materialized views daily at 03:00 UTC:

```sql
-- Example: Refresh Comunicación view
CREATE OR REPLACE VIEW `BI_ENLA.v_callao_comunicacion_2026` AS
SELECT * FROM `BI_ENLA.v_callao_comunicacion_2026_latest`;
```

Schedule via BigQuery > Scheduled Queries > Create Schedule.

---

## Monitoring and Alerting

### Cloud Logging

```bash
# View Cloud Function logs
gcloud functions logs read enla-pipeline-orchestrator --limit 50

# Filter for errors
gcloud functions logs read enla-pipeline-orchestrator \
  --severity ERROR \
  --limit 20
```

### BigQuery Monitoring

```bash
# Check recent pipeline runs
bq query --use_legacy_sql=false "
SELECT *
FROM \`YOUR_PROJECT_ID.BI_ENLA.pipeline_runs\`
ORDER BY start_time DESC
LIMIT 10
"
```

### Alert Configuration

Alerts are sent via SendGrid when:
- High-risk institutions are detected (ALTO risk level)
- Pipeline execution fails
- Model confidence drops below threshold

Configure alert recipients in Terraform:
```hcl
alert_emails = ["admin@example.com", "principal@school.edu"]
```

---

## Troubleshooting

### Pipeline Fails at Ingestion

**Symptom**: Cloud Function fails during Excel ingestion

**Diagnosis**:
```bash
gcloud functions logs read enla-pipeline-orchestrator --severity ERROR
```

**Common Causes**:
1. MongoDB connection failed → Check `MONGODB_URI` secret
2. Excel file format changed → Check file against schema
3. Permissions issue → Verify service account IAM roles

### BigQuery Table Not Found

**Symptom**: dbt run fails with "relation not found"

**Solution**:
```bash
# Verify tables exist
bq ls YOUR_PROJECT_ID:BI_ENLA

# Run Python ETL to create tables
python -m src.etl.transform
```

### Cloud Function Timeout

**Symptom**: Function exceeds 540s timeout

**Solution**:
1. Check for slow MongoDB queries
2. Optimize BigQuery loads
3. Increase timeout (max 540s for 2nd gen)

### dbt Models Fail

**Symptom**: `dbt run` returns errors

**Diagnosis**:
```bash
dbt debug  # Check connection
dbt compile  # Check compiled SQL
```

**Common Causes**:
1. Source tables don't exist → Run Python ETL first
2. BigQuery permissions → Check service account roles
3. SQL syntax error → Check model SQL

---

## Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| SEV1 | Pipeline down, no predictions | < 1 hour |
| SEV2 | Partial failure, some areas affected | < 4 hours |
| SEV3 | Non-critical issue, dashboard lag | < 1 day |

### SEV1 Response: Pipeline Down

1. **Detect**: Alert received or dashboard shows no data
2. **Verify**: Check Cloud Function logs
   ```bash
   gcloud functions logs read enla-pipeline-orchestrator --limit 20
   ```
3. **Mitigate**:
   - Check GCP service status
   - Verify secrets in Secret Manager
   - Restart function if needed
4. **Resolve**: Fix root cause (code bug, config issue, etc.)
5. **Post-mortem**: Document incident and preventive measures

### SEV2 Response: Partial Failure

1. Check which area/phase failed
2. Re-run specific pipeline phase
3. Verify data consistency in BigQuery
4. Update dashboards if needed

### Emergency Contacts

| Role | Contact | Email |
|------|---------|-------|
| Technical Lead | TBD | tech-lead@example.com |
| Data Engineer | TBD | data-eng@example.com |
| School Admin | TBD | admin@example.com |

---

## Appendix: Quick Reference

### Useful Commands

```bash
# Terraform
terraform init/plan/apply/destroy

# gcloud
gcloud functions describe enla-pipeline-orchestrator
gcloud pubsub topics publish enla-raw-data-ready --message '{}'

# bq
bq query "SELECT COUNT(*) FROM BI_ENLA.enla_callao_features"
bq show BI_ENLA

# dbt
dbt run/test/debug/docs
```

### File Locations

| Component | Path |
|-----------|------|
| Terraform configs | `terraform/` |
| Cloud Function | `gcp/functions/enla_orchestrator/` |
| dbt models | `dbt/models/` |
| Python source | `src/` |
| Documentation | `docs/` |
