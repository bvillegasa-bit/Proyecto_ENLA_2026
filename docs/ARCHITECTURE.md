# ENLA 2026 Callao - Architecture Document

> **System Architecture Overview**
> Last Updated: 2026-05-01

## Executive Summary

The ENLA 2026 Callao system is a machine learning prediction platform that forecasts academic success for educational institutions in Callao, Peru. The system processes historical academic data through a complete pipeline: ingestion → transformation → feature engineering → model training → prediction → alerting → visualization.

**Key Metrics:**
- 4 academic areas: Comunicación, Matemática, CCSS, CyT
- 540-second pipeline execution timeout
- 5 Looker Studio dashboards
- Daily predictions with 03:00 UTC refresh

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                            │
│                    (Excel Files - Manual Upload)                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SPRINT 1: INGESTION                        │
│                  (Excel → MongoDB)                              │
│  • ingest_enla.py    • validators.py    • config.py            │
│  • mongo_client.py                                               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SPRINT 2: ETL                             │
│              (MongoDB → BigQuery Data Warehouse)                │
│  • bigquery_client.py    • transform.py    • schemas.py        │
│  • 23 tests                                                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SPRINT 3: FEATURES                         │
│                    (Feature Engineering)                        │
│  • engineer.py    • schemas.py    • 54 tests                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SPRINT 4: MODELS                           │
│              (ML Training & Prediction)                          │
│  • trainer.py    • predictor.py    • 5 SQL templates           │
│  • 63 tests                                                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SPRINT 5: ALERTING                         │
│                  (Email Alerts + Cloud Functions)               │
│  • email_alert.py    • orchestrator    • 23+ tests             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SPRINT 6: VISUALIZATION                       │
│              (Infrastructure + Dashboards)                      │
│  • Terraform (IaC)    • dbt (Transformations)                 │
│  • Looker Studio (5 Dashboards)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Data Ingestion (Sprint 1)

**Purpose**: Load Excel data into MongoDB for processing.

| Component | File | Description |
|-----------|------|-------------|
| Ingest Script | `src/ingestion/ingest_enla.py` | Main ingestion logic |
| Validators | `src/ingestion/validators.py` | Data validation rules |
| Config | `src/ingestion/config.py` | Configuration settings |
| MongoDB Client | `src/database/mongo_client.py` | MongoDB connection handling |

**Data Flow**: Excel → pandas DataFrame → validation → MongoDB

### 2. ETL Pipeline (Sprint 2)

**Purpose**: Transform and load data from MongoDB to BigQuery.

| Component | File | Description |
|-----------|------|-------------|
| BigQuery Client | `src/etl/bigquery_client.py` | BigQuery connection and operations |
| Transform | `src/etl/transform.py` | Data transformation logic |
| Schemas | `src/etl/schemas.py` | BigQuery table schemas |

**Data Flow**: MongoDB → transform → BigQuery (fact tables + staging)

### 3. Feature Engineering (Sprint 3)

**Purpose**: Create ML-ready features from raw data.

| Component | File | Description |
|-----------|------|-------------|
| Engineer | `src/features/engineer.py` | Feature creation logic |
| Schemas | `src/features/schemas.py` | Feature table schema |

**Features Created**:
- `avg_score_2023`, `avg_score_2022`, `avg_score_2021`
- `trend` (score trend over time)
- `variance` (score variance)
- `target` (binary target variable)

### 4. ML Models (Sprint 4)

**Purpose**: Train models and generate predictions for 2026.

| Component | File | Description |
|-----------|------|-------------|
| Trainer | `src/models/trainer.py` | Model training pipeline |
| Predictor | `src/models/predictor.py` | Prediction generation |
| SQL Templates | `src/models/sql/` | 5 area-specific SQL templates |

**Output**:
- `predicted_success` (binary: 0/1)
- `confidence` (0-1 score)
- `risk_level` (ALTO/MEDIO/BAJO)

### 5. Alerting (Sprint 5)

**Purpose**: Notify stakeholders of high-risk institutions.

| Component | File | Description |
|-----------|------|-------------|
| Email Alert | `src/alerting/email_alert.py` | SendGrid email alerts |
| Orchestrator | `gcp/functions/enla_orchestrator/` | Cloud Function orchestrator |

**Triggers**:
- High-risk count > threshold
- Pipeline failure
- Weekly summary

### 6. Infrastructure & Visualization (Sprint 6)

**Purpose**: Deploy infrastructure as code and create dashboards.

#### Terraform Infrastructure (`terraform/`)

| Resource | Name | Purpose |
|----------|------|---------|
| BigQuery Dataset | `BI_ENLA` | Data warehouse |
| GCS Bucket | `enla-raw-data-{project_id}` | Raw file storage |
| Pub/Sub Topic | `enla-raw-data-ready` | Pipeline trigger |
| Cloud Function | `enla-pipeline-orchestrator` | Orchestration |
| Secret Manager | `MONGODB_URI`, `SENDGRID_API_KEY` | Credentials |

#### dbt Transformations (`dbt/`)

| Model | Type | Purpose |
|-------|------|---------|
| `enla_callao_features` | Table | Feature store |
| `enla_callao_predictions_2026` | Table | Predictions |
| `v_callao_comunicacion_2026` | View | Dashboard source |
| `v_callao_matematica_2026` | View | Dashboard source |
| `v_callao_ccss_2026` | View | Dashboard source |
| `v_callao_cyt_2026` | View | Dashboard source |
| `v_callao_resumen_todas_areas` | View | Executive summary |

#### Looker Studio Dashboards

1. **Comunicación Dashboard**: Trends, risk distribution, KPIs
2. **Matemática Dashboard**: Same structure
3. **CCSS Dashboard**: Same structure
4. **CyT Dashboard**: Same structure
5. **Executive Summary**: Aggregate across all areas

---

## Data Model

### BigQuery Schema

```
BI_ENLA (Dataset)
├── enla_raw (Staging table from MongoDB)
├── fact_enla (Cleaned fact table)
├── enla_callao_features (Feature table)
├── enla_callao_predictions_2026 (Predictions)
├── v_callao_comunicacion_2026 (Dashboard view)
├── v_callao_matematica_2026 (Dashboard view)
├── v_callao_ccss_2026 (Dashboard view)
├── v_callao_cyt_2026 (Dashboard view)
└── v_callao_resumen_todas_areas (Executive summary view)
```

### MongoDB Schema

```
enla_db (Database)
└── enla_callao (Collection)
    ├── institution_id (string)
    ├── nom_ie (string)
    ├── area (string: comunicacion/matematica/ccss/cyt)
    ├── score_2023 (float)
    ├── score_2022 (float)
    └── score_2021 (float)
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.11 |
| Data Processing | pandas | 1.5.3 |
| Database (NoSQL) | MongoDB | (Atlas) |
| Data Warehouse | BigQuery | - |
| ML Framework | scikit-learn | (latest) |
| IaC | Terraform | >= 1.3.0 |
| Transformation | dbt | 1.5.0 |
| Visualization | Looker Studio | - |
| Alerting | SendGrid | - |
| Cloud Functions | Google Cloud Functions v2 | Python 3.11 |

---

## Security & IAM

### Service Account Roles

| Role | Permissions |
|------|-------------|
| `enla-orchestrator-sa` | BigQuery dataEditor, jobUser |
| | Storage objectViewer, objectCreator |
| | Pub/Sub subscriber, publisher |
| | Secret Manager secretAccessor |
| | Logging logWriter |

### Secret Management

| Secret | Storage | Access |
|--------|---------|--------|
| `MONGODB_URI` | Secret Manager | Cloud Function |
| `SENDGRID_API_KEY` | Secret Manager | Cloud Function |

---

## Monitoring & Observability

### Logging

- **Cloud Function**: Cloud Logging (`enla-pipeline-orchestrator`)
- **BigQuery**: Query history and job logs
- **Python apps**: structlog with JSON formatter

### Metrics

| Metric | Source | Purpose |
|--------|--------|---------|
| Pipeline duration | Cloud Function logs | Performance monitoring |
| Prediction count | BigQuery | Data validation |
| Model accuracy | BigQuery `model_metrics` | Model quality |
| Alert count | SendGrid | Engagement tracking |

### Alerting

- Email alerts via SendGrid for high-risk institutions
- Cloud Function failure notifications (future: Cloud Monitoring alerts)

---

## Scalability & Performance

### Current Limits

- Cloud Function timeout: 540 seconds
- Cloud Function memory: 512 MB
- BigQuery: Unlimited (pay-per-query)

### Future Considerations

- Migrate to Cloud Run for longer-running pipelines
- Implement incremental processing for large datasets
- Add caching layer for frequently accessed predictions
- Consider BigQuery ML for in-database model training

---

## Disaster Recovery

### Backup Strategy

| Component | Backup Method | Retention |
|-----------|---------------|-----------|
| BigQuery data | Time Travel (7 days) | 7 days |
| GCS raw files | Versioning enabled | 90 days |
| MongoDB | Atlas backups | 30 days |

### Recovery Procedures

1. **Data corruption**: Restore from BigQuery snapshot or MongoDB backup
2. **Pipeline failure**: Re-run from failed phase
3. **Infrastructure loss**: `terraform apply` to recreate resources

---

## Appendix: File Structure

```
enla-2026-callao/
├── config/                 # Configuration files
├── data/                   # Data files (raw, processed)
├── dbt/                    # dbt transformations
│   ├── models/             # dbt models (views, tables)
│   ├── seeds/              # Seed data
│   └── macros/             # dbt macros
├── docs/                   # Documentation
│   ├── RUNBOOK.md          # Operational runbook
│   ├── ARCHITECTURE.md     # This file
│   └── DASHBOARD_SPEC.md   # Dashboard specifications
├── gcp/                    # GCP-specific code
│   ├── bigquery/           # BigQuery scripts
│   └── functions/         # Cloud Functions
│       └── enla_orchestrator/
├── src/                    # Python source code
│   ├── ingestion/          # Sprint 1
│   ├── etl/                # Sprint 2
│   ├── features/           # Sprint 3
│   ├── models/             # Sprint 4
│   └── alerting/           # Sprint 5
├── terraform/              # Sprint 6 - IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── cloud_function.tf
│   └── iam.tf
├── tests/                  # All tests (140+ total)
└── requirements.txt        # Python dependencies
```
