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
    condition     = can(regex("^keplerops-nested-host-v[0-9]{8}[a-z0-9-]*$", var.image_name))
    error_message = "Image name must be an immutable dated KeplerOps image name."
  }
}

variable "zone" {
  type    = string
  default = "europe-west4-a"
}

variable "network" {
  type = string
}

variable "subnetwork" {
  type = string
}

variable "network_tags" {
  type        = list(string)
  description = "Caller-supplied tags granting bounded SSH/IAP ingress and package egress to the temporary builder."
}

variable "use_iap" {
  type    = bool
  default = false
}

source "googlecompute" "nested_host" {
  access_token            = var.access_token
  project_id              = var.project_id
  source_image            = "ubuntu-2404-noble-amd64-v20260723"
  source_image_project_id = ["ubuntu-os-cloud"]
  zone                    = var.zone
  network                 = var.network
  subnetwork              = var.subnetwork
  tags                    = var.network_tags
  ssh_username            = "packer"
  use_iap                 = var.use_iap
  machine_type            = "e2-standard-2"
  disk_size               = 100
  disk_type               = "pd-balanced"
  image_name              = var.image_name
  image_description       = "KeplerOps nested host: KVM, libvirt, dnsmasq, OVMF, Docker, pywinrm, NTFS, and hivex."
  image_storage_locations = ["eu"]
  image_licenses = [
    "projects/vm-options/global/licenses/enable-vmx",
  ]
}

build {
  name    = "keplerops-nested-host"
  sources = ["source.googlecompute.nested_host"]

  provisioner "shell" {
    inline = [
      "set -eu",
      "sudo apt-get update -qq",
      "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends dnsmasq-base docker.io jq libhivex-bin libvirt-clients libvirt-daemon-system ntfs-3g ovmf python3-winrm qemu-system-x86",
      "sudo systemctl enable docker libvirtd",
      "sudo apt-get clean",
      "sudo rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*",
      "sudo cloud-init clean --logs --seed",
    ]
  }
}
