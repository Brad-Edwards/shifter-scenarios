// Polaris range-host (polaris-vm) GCE custom image.
//
// A Debian 12 Docker host running the Polaris Compose stack (17 containers
// including a14-kali, dns and a9-splice), with the host sshd on the management
// port so a14-kali can bind host :22 and :3389. The stack is the reviewed
// build-v1.tar.gz from this repository, uploaded from the checkout and verified
// against its sidecar digest. No service account is attached to the builder, so
// the captured image carries no build identity.
//
// Claude Code is not part of this image. Shifter delivers it to the range host's
// /opt/shifter/bin at realization; Compose bind-mounts that directory into
// a14-kali.
packer {
  required_version = ">= 1.11.0, < 2.0.0"
  required_plugins {
    googlecompute = {
      source  = "github.com/hashicorp/googlecompute"
      version = ">= 1.1.9, < 1.2.0"
    }
  }
}

variable "project_id" {
  type = string
}

variable "access_token" {
  type      = string
  sensitive = true
}

variable "image_name" {
  type = string
  validation {
    condition     = can(regex("^shifter-polaris-vm-v[0-9]{8}[a-z0-9-]*$", var.image_name))
    error_message = "Image name must be an immutable dated shifter-polaris-vm image name."
  }
}

variable "source_revision" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{7,40}$", var.source_revision))
    error_message = "Source revision must be a git commit id."
  }
}

variable "stack_sha256" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.stack_sha256))
    error_message = "Stack digest must be a SHA-256 hex digest."
  }
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "network" {
  type = string
}

variable "subnetwork" {
  type = string
}

variable "use_iap" {
  type    = bool
  default = true
}

source "googlecompute" "polaris_vm" {
  access_token            = var.access_token
  project_id              = var.project_id
  source_image_family     = "debian-12"
  source_image_project_id = ["debian-cloud"]
  zone                    = var.zone
  network                 = var.network
  subnetwork              = var.subnetwork
  ssh_username            = "packer"
  use_internal_ip         = var.use_iap
  omit_external_ip        = var.use_iap
  use_iap                 = var.use_iap
  // IAP answers "Failed to lookup instance" until a new instance propagates,
  // which can outlast the plugin's default 30-second tunnel launch window.
  iap_tunnel_launch_wait = 300
  machine_type           = "e2-standard-8"
  // Docker Engine plus the built stack needs generous headroom.
  disk_size                       = 200
  disk_type                       = "pd-balanced"
  disable_default_service_account = true
  image_name                      = var.image_name
  image_family                    = "shifter-polaris-vm"
  image_description               = "Polaris range host: Debian Docker host running the Polaris Compose stack (no Claude Code)"
  image_storage_locations         = ["us"]
  image_labels = {
    image-type      = "polaris-vm"
    managed-by      = "packer"
    source-revision = var.source_revision
  }
}

build {
  name    = "polaris-vm"
  sources = ["source.googlecompute.polaris_vm"]

  provisioner "file" {
    source      = "${path.root}/../build/build-v1.tar.gz"
    destination = "/tmp/build-v1.tar.gz"
  }

  provisioner "file" {
    source      = "${path.root}/../../runtime-adapter/src/shifter_panw_adapter/assets/polaris-splice-credential.py"
    destination = "/tmp/polaris-splice-credential.py"
  }

  provisioner "shell" {
    environment_vars = ["POLARIS_STACK_SHA256=${var.stack_sha256}"]
    scripts = [
      "${path.root}/scripts/host-setup.sh",
      "${path.root}/scripts/stage-stack.sh",
      "${path.root}/scripts/cleanup.sh",
    ]
    execute_command = "sudo -S bash -c '{{ .Vars }} {{ .Path }}'"
  }
}
