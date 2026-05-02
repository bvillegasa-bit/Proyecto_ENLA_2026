# ==========================================
# ENLA 2026 Callao - Main Terraform Configuration
# Sprint 6: Infrastructure as Code
# ==========================================

terraform {
  required_version = ">= 1.3.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ==========================================
# Local Values
# ==========================================

locals {
  environment   = var.environment
  project_id    = var.project_id
  gcs_bucket_name = "enla-raw-data-${var.project_id}"
  pubsub_topic_name = "enla-raw-data-ready"
  dataset_id    = "BI_ENLA"
}

# ==========================================
# BigQuery Dataset
# ==========================================

resource "google_bigquery_dataset" "bi_enla" {
  dataset_id    = local.dataset_id
  friendly_name = "ENLA 2026 Callao Business Intelligence"
  description   = "Dataset for ENLA 2026 Callao ML predictions and analytics"
  location      = "US"

  labels = {
    environment = local.environment
    project     = "enla-2026-callao"
    sprint      = "sprint6"
  }
}

# ==========================================
# Cloud Storage Bucket for Raw Data
# ==========================================

resource "google_storage_bucket" "raw_data" {
  name          = local.gcs_bucket_name
  location      = "US"
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = local.environment
    purpose     = "raw-data-ingestion"
  }
}

# ==========================================
# Pub/Sub Topic for Pipeline Trigger
# ==========================================

resource "google_pubsub_topic" "raw_data_ready" {
  name = local.pubsub_topic_name

  labels = {
    environment = local.environment
    purpose     = "pipeline-trigger"
  }
}

# ==========================================
# Secret Manager Secrets
# ==========================================

resource "google_secret_manager_secret" "mongodb_uri" {
  secret_id = "MONGODB_URI"

  replication {
    auto {}
  }

  labels = {
    environment = local.environment
  }
}

resource "google_secret_manager_secret" "sendgrid_api_key" {
  secret_id = "SENDGRID_API_KEY"

  replication {
    auto {}
  }

  labels = {
    environment = local.environment
  }
}

# ==========================================
# BigQuery Scheduled Queries (Materialized Views Refresh)
# ==========================================

# Note: Scheduled queries are created via BigQuery Data Transfer Service
# The materialized views are defined in dbt/models and refreshed daily at 03:00 UTC
# This is configured through BigQuery's native scheduling, not Cloud Scheduler

# ==========================================
# Looker Studio Dashboard Links (Output only)
# ==========================================

# Dashboard URLs are generated after manual creation in Looker Studio
# See docs/DASHBOARD_SPEC.md for dashboard specifications
