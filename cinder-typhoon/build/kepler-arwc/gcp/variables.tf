variable "project_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a canonical GCP project ID."
  }
}

variable "region" {
  type    = string
  default = "us-central1"
}
