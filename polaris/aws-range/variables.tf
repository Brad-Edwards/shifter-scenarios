variable "aws_region" {
  description = "AWS region for the standalone range."
  type        = string
  default     = "us-east-2"

  validation {
    condition     = var.aws_region == "us-east-2"
    error_message = "The pinned Polaris event-range AMIs are validated only in us-east-2."
  }
}

variable "ubuntu_ami_id" {
  description = "Pinned Ubuntu 24.04 AMI validated by the Polaris live rehearsal in us-east-2."
  type        = string
  default     = "ami-0dc6aa44dbcdd872e"
}

variable "windows_ami_id" {
  description = "Pinned Windows Server 2022 AMI validated by the Polaris live rehearsal in us-east-2."
  type        = string
  default     = "ami-0a309571b4f421554"
}

variable "range_id" {
  description = "Unique lowercase identifier used to namespace all live rehearsal resources."
  type        = string

  validation {
    condition     = can(regex("^polaris-[a-z0-9]{12}$", var.range_id))
    error_message = "range_id must match polaris-[a-z0-9]{12}."
  }
}

variable "range_indices" {
  description = "String indices of the POLARIS ranges to provision. Each index gets its own /28 subnet + polaris VM + A2 DC. Default is a single range so a plain `terraform apply` still produces one working range."
  type        = list(string)
  default     = ["0"]

  validation {
    condition     = length(var.range_indices) == length(toset(var.range_indices))
    error_message = "range_indices must be unique."
  }
}

variable "polaris_cidr_block" {
  description = "Base CIDR allocated to POLARIS. Carved into /28 subnets via cidrsubnet(block, 4, i), so a /24 yields 16 ranges, a /22 yields 64, a /21 yields 128. Default /24 holds the single-range smoke case + room to grow up to 16 without re-planning the VPC."
  type        = string
  default     = "10.77.0.0/24"
}

variable "availability_zone" {
  description = "AZ for the standalone POLARIS subnet."
  type        = string
  default     = "us-east-2a"
}

variable "participant_cidr" {
  description = "Public IPv4 /32 allowed to reach A14 SSH and RDP."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.participant_cidr)) && endswith(var.participant_cidr, "/32")
    error_message = "participant_cidr must be a single IPv4 /32."
  }
}

variable "instance_type" {
  description = "EC2 instance type. Kali GUI + 17 compose containers need plenty of headroom."
  type        = string
  default     = "m5.2xlarge"
}

variable "kali_authorized_key" {
  description = "Ephemeral participant OpenSSH public key injected into A14's kali authorized_keys. A public key is not secret."
  type        = string
  default     = ""
}

variable "a2_instance_type" {
  description = "EC2 instance type for the A2 Windows DCs. t3.large (2 vCPU, 8 GB RAM) is the smallest that keeps AD DS + DNS responsive under Kerberoast + secretsdump load."
  type        = string
  default     = "t3.large"
}

variable "a2_administrator_password" {
  description = "Synthetic scenario password set on the Windows Administrator account at first boot and used by the participant walkthrough."
  type        = string
  default     = "CortexSavesTheDay!"
  sensitive   = true
}

variable "a2_dsrm_password" {
  description = "Directory Services Restore Mode password. Only ever used during Install-ADDSForest; cannot be discovered from outside the box so the value is intentionally trivial."
  type        = string
  default     = "DsrmR3store!2026"
  sensitive   = true
}
