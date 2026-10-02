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

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "instance_name" {
  type    = string
  default = "cinder-arwc-golden"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-4"
}
