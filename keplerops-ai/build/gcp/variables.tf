variable "project_id" {
  description = "Existing GCP project that contains the isolated range tenant."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a canonical GCP project id."
  }
}

variable "range_instance" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$", var.range_instance))
    error_message = "range_instance must be a lowercase, collision-safe namespace."
  }
}

variable "participant" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$", var.participant))
    error_message = "participant must be a lowercase, collision-safe namespace."
  }
}

variable "region" {
  type    = string
  default = "europe-west4"
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.region))
    error_message = "region must be a canonical GCP region."
  }
}

variable "zone" {
  type    = string
  default = "europe-west4-a"
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+-[a-z]$", var.zone))
    error_message = "zone must be a canonical GCP zone."
  }
}

variable "participant_source_cidrs" {
  description = "Compatibility input; participant ingress is enforced by the deployment-cell firewall policy."
  type        = list(string)
  validation {
    condition = length(var.participant_source_cidrs) > 0 && alltrue([
      for cidr in var.participant_source_cidrs :
      can(cidrnetmask(cidr)) && cidr != "0.0.0.0/0"
    ])
    error_message = "participant_source_cidrs must be valid and may not be world-open."
  }
}

variable "range_subnet_self_link" {
  description = "Cell-owned subnet allocated to this range."
  type        = string
  validation {
    condition     = can(regex("^https://www.googleapis.com/compute/v1/projects/.+/regions/.+/subnetworks/.+$", var.range_subnet_self_link))
    error_message = "range_subnet_self_link must be a canonical Compute Engine subnetwork self link."
  }
}

variable "range_subnet_cidr" {
  description = "CIDR of the cell-owned subnet allocated to this range."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.range_subnet_cidr))
    error_message = "range_subnet_cidr must be a valid CIDR."
  }
}

variable "runtime_repository_id" {
  description = "Cell-owned shared immutable Artifact Registry repository id."
  type        = string
}

variable "runtime_repository_location" {
  description = "Region containing the cell-owned runtime repository."
  type        = string
  default     = "europe-west4"
}

variable "shared_model_service_name" {
  description = "Cell-owned IAM-protected Cloud Run model service name."
  type        = string
  validation {
    condition     = can(regex("^keplerops-model-[a-z0-9][a-z0-9-]{0,48}$", var.shared_model_service_name))
    error_message = "shared_model_service_name must identify the cell-owned KeplerOps model service."
  }
}

variable "shared_model_service_url" {
  description = "Cell-owned internal Cloud Run URL used as both model endpoint and identity-token audience."
  type        = string
  validation {
    condition     = can(regex("^https://keplerops-model-[a-z0-9-]+-[a-z0-9]+\\.[a-z0-9-]+\\.run\\.app$", var.shared_model_service_url))
    error_message = "shared_model_service_url must be the canonical HTTPS Cloud Run service URL."
  }
}

variable "cos_image" {
  description = "Immutable Container-Optimized OS image, never an image family."
  type        = string
  default     = "projects/cos-cloud/global/images/cos-121-18867-381-183"
  validation {
    condition = can(regex(
      "^projects/cos-cloud/global/images/cos-[0-9]+-[0-9]+-[0-9]+-[0-9]+$",
      var.cos_image,
    ))
    error_message = "cos_image must name one immutable COS image."
  }
}

variable "nested_host_image" {
  description = "Immutable Ubuntu image with the KeplerOps nested-host prerequisites."
  type        = string
  validation {
    condition     = can(regex("^projects/[^/]+/global/images/[^/]+$", var.nested_host_image))
    error_message = "nested_host_image must name one immutable GCE image, never a family."
  }
}

variable "nested_host_machine_type" {
  description = "Outer packed-host shape; 12 vCPU permits 200 ranges within the current 2400-vCPU quota."
  type        = string
  default     = "n2-custom-12-98304"
  validation {
    condition     = can(regex("^n2-custom-[0-9]+-[0-9]+$", var.nested_host_machine_type))
    error_message = "nested_host_machine_type must be an explicit N2 custom shape."
  }
}

variable "nested_host_disk_gib" {
  description = "Packed Docker estate disk size on the outer host."
  type        = number
  default     = 250
  validation {
    condition     = var.nested_host_disk_gib >= 200 && var.nested_host_disk_gib <= 512
    error_message = "nested_host_disk_gib must be between 200 and 512 GiB."
  }
}

variable "windows_image" {
  description = "Immutable Windows Server image used for the DC and endpoint-role hosts."
  type        = string
  validation {
    condition     = can(regex("^projects/[^/]+/global/images/[^/]+$", var.windows_image))
    error_message = "windows_image must name one immutable GCE image, never a family."
  }
}

variable "image_lock_file" {
  description = "Generated digest lock written by publish-images.py."
  type        = string
  default     = "../.operator/image-lock.json"
}

variable "sdl_realization_file" {
  description = "Ephemeral GCP projection rendered directly from the canonical modular ACES SDL."
  type        = string
  default     = "../.operator/sdl-realization.json"
}

variable "deploy_runtime" {
  description = "False for the foundation/image-publish phase; true for runtime nodes."
  type        = bool
  default     = true
}

variable "telemetry_capture_signals" {
  description = "Independently enabled encrypted full-content signals; operational telemetry is unaffected."
  type = object({
    prompt              = bool
    completion          = bool
    tool_call           = bool
    tool_result         = bool
    terminal_command    = bool
    terminal_input      = bool
    terminal_output     = bool
    process_lifecycle   = bool
    browser_interaction = bool
    notebook_content    = bool
    file_content        = bool
    workflow_state      = bool
    artifact_content    = bool
    http_body           = bool
  })
  default = {
    prompt              = false
    completion          = false
    tool_call           = false
    tool_result         = false
    terminal_command    = false
    terminal_input      = false
    terminal_output     = false
    process_lifecycle   = false
    browser_interaction = false
    notebook_content    = false
    file_content        = false
    workflow_state      = false
    artifact_content    = false
    http_body           = false
  }
}
