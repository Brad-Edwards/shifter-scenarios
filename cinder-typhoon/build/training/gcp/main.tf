locals {
  labels = {
    scenario     = "cinder-typhoon"
    segment      = "training"
    purpose      = "golden-range"
    "managed-by" = "shifter-scenarios"
  }
}

resource "google_project_service" "compute" {
  project            = var.project_id
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_compute_network" "training" {
  name                    = "cinder-training-golden"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  depends_on              = [google_project_service.compute]
}

resource "google_compute_subnetwork" "carrier" {
  name                     = "cinder-training-carrier"
  ip_cidr_range            = "10.77.39.0/28"
  region                   = var.region
  network                  = google_compute_network.training.id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "EXCLUDE_ALL_METADATA"
  }
}

resource "google_compute_router" "training" {
  name    = "cinder-training-golden"
  region  = var.region
  network = google_compute_network.training.id
}

resource "google_compute_router_nat" "training" {
  name                               = "cinder-training-golden"
  router                             = google_compute_router.training.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.carrier.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

resource "google_compute_firewall" "iap_ssh" {
  name          = "cinder-training-golden-iap-ssh"
  network       = google_compute_network.training.name
  direction     = "INGRESS"
  priority      = 900
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["cinder-training-carrier"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  log_config {
    metadata = "EXCLUDE_ALL_METADATA"
  }
}

resource "google_service_account" "carrier" {
  account_id   = "cinder-training-carrier"
  display_name = "Cinder Training golden-range carrier"
  description  = "Keyless identity with no project roles for the private Training carrier"
}

resource "google_compute_instance" "carrier" {
  name                      = var.instance_name
  machine_type              = var.machine_type
  zone                      = var.zone
  allow_stopping_for_update = true
  can_ip_forward            = false
  deletion_protection       = false
  tags                      = ["cinder-training-carrier"]
  labels                    = local.labels

  boot_disk {
    auto_delete = true
    initialize_params {
      image  = "projects/debian-cloud/global/images/debian-12-bookworm-v20260921"
      size   = 40
      type   = "pd-balanced"
      labels = local.labels
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.carrier.id
    network_ip = "10.77.39.2"
  }

  service_account {
    email  = google_service_account.carrier.email
    scopes = []
  }

  metadata = {
    enable-oslogin            = "TRUE"
    block-project-ssh-keys    = "TRUE"
    serial-port-enable        = "FALSE"
    enable-guest-attributes   = "FALSE"
    google-logging-enabled    = "FALSE"
    google-monitoring-enabled = "FALSE"
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/sh
    set -eu
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install --no-install-recommends -y ca-certificates curl git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian %s stable\n' "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install --no-install-recommends -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    install -d -m 0755 /opt/cinder-typhoon
    touch /var/lib/cinder-training-carrier-ready
  SCRIPT

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  depends_on = [google_compute_router_nat.training]
}
