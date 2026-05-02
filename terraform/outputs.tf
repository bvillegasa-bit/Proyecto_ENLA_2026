# ==========================================
# ENLA 2026 Callao - Terraform Output Values
# Sprint 6: Infrastructure as Code
# ==========================================

output "bigquery_dataset_id" {
  description = "The ID of the BigQuery dataset"
  value       = google_bigquery_dataset.bi_enla.dataset_id
}

output "bigquery_dataset_full_id" {
  description = "The fully qualified BigQuery dataset ID"
  value       = "${var.project_id}:${google_bigquery_dataset.bi_enla.dataset_id}"
}

output "gcs_bucket_name" {
  description = "The name of the GCS bucket for raw data"
  value       = google_storage_bucket.raw_data.name
}

output "gcs_bucket_url" {
  description = "The URL of the GCS bucket"
  value       = "gs://${google_storage_bucket.raw_data.name}"
}

output "pubsub_topic_id" {
  description = "The ID of the Pub/Sub topic"
  value       = google_pubsub_topic.raw_data_ready.name
}

output "pubsub_topic_full_path" {
  description = "The full path of the Pub/Sub topic"
  value       = "projects/${var.project_id}/topics/${google_pubsub_topic.raw_data_ready.name}"
}

output "cloud_function_name" {
  description = "The name of the Cloud Function"
  value       = google_cloudfunctions2_function.orchestrator_function.name
}

output "cloud_function_url" {
  description = "The URL of the Cloud Function (HTTPS trigger)"
  value       = google_cloudfunctions2_function.orchestrator_function.service_config[0].uri
}

output "cloud_function_service_account" {
  description = "The service account used by the Cloud Function"
  value       = local.function_service_account_id
}

output "secret_manager_secrets" {
  description = "The Secret Manager secret IDs"
  value = {
    mongodb_uri     = google_secret_manager_secret.mongodb_uri.secret_id
    sendgrid_api_key = google_secret_manager_secret.sendgrid_api_key.secret_id
  }
}

output "dashboard_specification" {
  description = "Location of dashboard specification document"
  value       = "docs/DASHBOARD_SPEC.md"
}

output "infrastructure_summary" {
  description = "Summary of deployed infrastructure"
  value = <<-EOT
    ENLA 2026 Callao Infrastructure Summary:
    ==========================================
    Project:         ${var.project_id}
    Environment:     ${var.environment}
    Region:          ${var.region}
    
    BigQuery Dataset: ${google_bigquery_dataset.bi_enla.dataset_id}
    GCS Bucket:      ${google_storage_bucket.raw_data.name}
    Pub/Sub Topic:   ${google_pubsub_topic.raw_data_ready.name}
    Cloud Function:  ${google_cloudfunctions2_function.orchestrator_function.name}
    
    Next Steps:
    1. Deploy Cloud Function: see docs/RUNBOOK.md
    2. Create dbt models: run 'dbt run' in dbt/ directory
    3. Set up Looker Studio dashboards: see docs/DASHBOARD_SPEC.md
  EOT
}
