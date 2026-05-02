# ==========================================
# ENLA 2026 Callao - IAM Bindings
# Sprint 6: Infrastructure as Code
# ==========================================

# ==========================================
# Service Account IAM Roles
# ==========================================

# BigQuery Data Editor - Required for writing to BigQuery tables
resource "google_project_iam_member" "function_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# BigQuery Job User - Required for running BigQuery jobs (queries, loads)
resource "google_project_iam_member" "function_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# Storage Object Viewer - Required for reading from GCS buckets
resource "google_project_iam_member" "function_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# Storage Object Creator - Required for writing to GCS buckets (logs, temp files)
resource "google_project_iam_member" "function_storage_creator" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# Pub/Sub Subscriber - Required for consuming Pub/Sub messages
resource "google_project_iam_member" "function_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# Pub/Sub Publisher - Required for publishing to Pub/Sub topics (chaining)
resource "google_project_iam_member" "function_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# Secret Manager Secret Accessor - Required for accessing secrets
resource "google_project_iam_member" "function_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# Logging Writer - Required for writing logs to Cloud Logging
resource "google_project_iam_member" "function_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.orchestrator_sa.email}"
}

# ==========================================
# Additional IAM for Manual Operations (Optional)
# ==========================================

# Service account for CI/CD operations (if using GitHub Actions, Cloud Build, etc.)
# Uncomment and customize as needed
#
# resource "google_service_account" "cicd_sa" {
#   account_id   = "enla-cicd-sa"
#   display_name = "ENLA CI/CD Service Account"
#   description  = "Service account for CI/CD pipeline operations"
# }
#
# resource "google_project_iam_member" "cicd_bigquery_admin" {
#   project = var.project_id
#   role    = "roles/bigquery.admin"
#   member  = "serviceAccount:${google_service_account.cicd_sa.email}"
# }

# ==========================================
# Custom Role for Least Privilege (Optional)
# ==========================================

# Uncomment to create a custom role with minimal permissions
#
# resource "google_project_iam_custom_role" "enla_orchestrator_role" {
#   role_id     = "enlaOrchestrator"
#   title       = "ENLA Pipeline Orchestrator"
#   description = "Minimal permissions for ENLA pipeline Cloud Function"
#   permissions = [
#     "bigquery.datasets.get",
#     "bigquery.tables.create",
#     "bigquery.tables.delete",
#     "bigquery.tables.get",
#     "bigquery.tables.getData",
#     "bigquery.tables.list",
#     "bigquery.tables.updateData",
#     "bigquery.jobs.create",
#     "storage.objects.get",
#     "storage.objects.create",
#     "storage.objects.delete",
#     "pubsub.subscriptions.consume",
#     "pubsub.topics.publish",
#     "secretmanager.versions.access",
#     "logging.logEntries.create"
#   ]
# }
