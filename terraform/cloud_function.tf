# ==========================================
# ENLA 2026 Callao - Cloud Function Configuration
# Sprint 6: Infrastructure as Code
# ==========================================

# ==========================================
# Service Account for Cloud Function
# ==========================================

resource "google_service_account" "orchestrator_sa" {
  account_id   = "enla-orchestrator-sa"
  display_name = "ENLA Pipeline Orchestrator Service Account"
  description  = "Service account for the ENLA pipeline Cloud Function"
}

# ==========================================
# Cloud Function (2nd Generation)
# ==========================================

resource "google_cloudfunctions2_function" "orchestrator_function" {
  name        = "enla-pipeline-orchestrator"
  location    = var.region
  description = "Orchestrates the ENLA 2026 Callao ML prediction pipeline"

  build_config {
    runtime     = "python311"
    entry_point = "enla_pipeline_orchestrator"

    source {
      storage_source {
        bucket = google_storage_bucket.raw_data.name
        object = "functions/enla_orchestrator.zip"
      }
    }
  }

  service_config {
    max_instance_count = 3
    min_instance_count = 0

    available_memory    = "512Mi"
    timeout_seconds    = 540
    service_account_email = google_service_account.orchestrator_sa.email

    environment_variables = {
      GCP_PROJECT     = var.project_id
      ENVIRONMENT     = var.environment
      ALERT_EMAILS    = join(",", var.alert_emails)
      LOG_LEVEL       = "INFO"
    }

    secret_environment_variables {
      key        = "MONGODB_URI"
      project_id = var.project_id
      secret     = google_secret_manager_secret.mongodb_uri.secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "SENDGRID_API_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.sendgrid_api_key.secret_id
      version    = "latest"
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.raw_data_ready.id

    retry_policy = "RETRY_POLICY_RETRY"
  }

  labels = {
    environment = var.environment
    sprint      = "sprint6"
  }

  depends_on = [
    google_secret_manager_secret.mongodb_uri,
    google_secret_manager_secret.sendgrid_api_key,
    google_storage_bucket.raw_data,
    google_service_account.orchestrator_sa
  ]
}

# ==========================================
# Cloud Function Source Code Upload
# ==========================================

# Note: The actual source code deployment is done via:
# gcloud functions deploy enla-pipeline-orchestrator --source=gcp/functions/enla_orchestrator/
#
# The zip file reference in build_config is for CI/CD pipelines.
# For manual deployment, use the gcloud command above.

# ==========================================
# Cloud Function IAM (Public HTTPS access - optional)
# ==========================================

# Allow unauthenticated invocations for the health check endpoint
# Comment out if you want to require authentication
resource "google_cloudfunctions2_function_iam_member" "invoker" {
  cloud_function = google_cloudfunctions2_function.orchestrator_function.name
  location       = var.region
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

# ==========================================
# Cloud Scheduler for Daily Pipeline (Optional)
# ==========================================

# Uncomment to enable scheduled daily runs at 02:00 UTC
# resource "google_cloud_scheduler_job" "daily_pipeline" {
#   name             = "enla-daily-pipeline"
#   description      = "Triggers the ENLA pipeline daily at 02:00 UTC"
#   schedule         = "0 2 * * *"
#   time_zone        = "UTC"
#   attempt_deadline = "540s"
#
#   pubsub_target {
#     topic_name = google_pubsub_topic.raw_data_ready.id
#     data       = base64encode(jsonencode({ "source": "scheduled", "model_version": "v1" }))
#   }
#
#   depends_on = [google_pubsub_topic.raw_data_ready]
# }
