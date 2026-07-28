variable "project_id" {
  description = "GCP project that owns the long-lived deployment cell."
  type        = string
}

variable "cell_id" {
  description = "Stable lowercase deployment-cell identifier."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$", var.cell_id))
    error_message = "cell_id must be a lowercase collision-safe identifier."
  }
}

variable "region" {
  type    = string
  default = "europe-west4"
}

variable "range_subnets" {
  description = "Preallocated range identifier to non-overlapping regional subnet CIDR."
  type        = map(string)
  validation {
    condition = length(var.range_subnets) > 0 && alltrue([
      for cidr in values(var.range_subnets) : can(cidrnetmask(cidr))
    ])
    error_message = "range_subnets must contain valid CIDRs."
  }
}

variable "participant_source_cidrs" {
  description = "Approved source CIDRs for participant browser access."
  type        = list(string)
  validation {
    condition = length(var.participant_source_cidrs) > 0 && alltrue([
      for cidr in var.participant_source_cidrs :
      can(cidrnetmask(cidr)) && cidr != "0.0.0.0/0"
    ])
    error_message = "participant_source_cidrs must be valid and not world-open."
  }
}

variable "shared_model_image" {
  description = "Digest-pinned KeplerOps vLLM image. Null creates only the cell foundation."
  type        = string
  default     = null
  nullable    = true
  validation {
    condition = (
      var.shared_model_image == null
      || can(regex(
        "^[a-z]+-[a-z]+[0-9]+-docker\\.pkg\\.dev/[^/]+/[^/]+/[^@]+@sha256:[0-9a-f]{64}$",
        var.shared_model_image,
      ))
    )
    error_message = "shared_model_image must be a regional Artifact Registry URI pinned by sha256 digest."
  }
}

variable "shared_model_min_instances" {
  description = "Warm shared inference capacity retained per deployment cell."
  type        = number
  default     = 1
  validation {
    condition     = var.shared_model_min_instances >= 1
    error_message = "shared_model_min_instances must retain at least one warm instance."
  }
}

variable "shared_model_max_instances" {
  description = "Hard deployment-cell GPU concurrency ceiling."
  type        = number
  default     = 4
  validation {
    condition     = var.shared_model_max_instances >= var.shared_model_min_instances
    error_message = "shared_model_max_instances must be at least shared_model_min_instances."
  }
}

variable "shared_model_request_concurrency" {
  description = "Maximum concurrent inference requests admitted by each GPU instance."
  type        = number
  default     = 8
  validation {
    condition     = var.shared_model_request_concurrency >= 1 && var.shared_model_request_concurrency <= 32
    error_message = "shared_model_request_concurrency must be between 1 and 32."
  }
}
