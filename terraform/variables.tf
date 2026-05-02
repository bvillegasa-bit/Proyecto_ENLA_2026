# ==========================================
# ENLA 2026 Callao - Terraform Input Variables
# Sprint 6: Infrastructure as Code
# ==========================================

variable "project_id" {
  description = "GCP Project ID where resources will be deployed"
  type        = string
  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty."
  }
}

variable "region" {
  description = "GCP region for deploying resources"
  type        = string
  default     = "us"

  validation {
    condition     = contains(["us", "us-central1", "us-east1", "europe-west1", "asia-east1"], var.region)
    error_message = "Region must be a valid GCP region."
  }
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["prod", "staging", "dev", "test"], var.environment)
    error_message = "Environment must be one of: prod, staging, dev, test."
  }
}

variable "mongodb_uri" {
  description = "MongoDB connection URI (sensitive - stored in Secret Manager)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.mongodb_uri) > 0
    error_message = "MongoDB URI must not be empty."
  }
}

variable "sendgrid_api_key" {
  description = "SendGrid API key for email alerts (sensitive - stored in Secret Manager)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.sendgrid_api_key) > 0
    error_message = "SendGrid API key must not be empty."
  }
}

variable "alert_emails" {
  description = "List of email addresses to receive alerts"
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for email in var.alert_emails : can(regex("^[^@]+@[^@]+\\.[^@]+$", email))
    ])
    error_message = "All alert emails must be valid email addresses."
  }
}

# ==========================================
# Local Variables (computed)
# ==========================================

locals {
  # Common labels applied to all resources
  common_labels = {
    project     = "enla-2026-callao"
    environment = var.environment
    managed_by  = "terraform"
    sprint      = "sprint6"
  }

  # Service account ID for Cloud Function
  function_service_account_id = "enla-orchestrator-sa@${var.project_id}.iam.gserviceaccount.com"
}
