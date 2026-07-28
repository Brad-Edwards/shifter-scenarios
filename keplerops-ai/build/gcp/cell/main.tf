locals {
  labels = {
    scenario     = "keplerops-ai"
    cell         = var.cell_id
    "managed-by" = "shifter-scenarios"
  }
  range_cidrs = sort(values(var.range_subnets))
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "dns.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "cell" {
  name                    = "keplerops-${var.cell_id}"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  depends_on              = [google_project_service.required]
}

resource "google_compute_subnetwork" "range" {
  for_each                 = var.range_subnets
  name                     = "kep-${var.cell_id}-${each.key}"
  ip_cidr_range            = each.value
  region                   = var.region
  network                  = google_compute_network.cell.id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "EXCLUDE_ALL_METADATA"
  }
}

resource "google_artifact_registry_repository" "runtime" {
  location      = var.region
  repository_id = "keplerops-${var.cell_id}"
  format        = "DOCKER"
  description   = "Shared immutable KeplerOps runtime images for deployment cell ${var.cell_id}"
  depends_on    = [google_project_service.required]
}

resource "google_service_account" "shared_model" {
  count        = var.shared_model_image == null ? 0 : 1
  account_id   = substr("kep-model-${replace(var.cell_id, "-", "")}", 0, 30)
  display_name = "KeplerOps shared model pool"
  description  = "Keyless execution identity for the stateless shared model pool in ${var.cell_id}"
}

resource "google_artifact_registry_repository_iam_member" "shared_model_reader" {
  count      = var.shared_model_image == null ? 0 : 1
  location   = google_artifact_registry_repository.runtime.location
  repository = google_artifact_registry_repository.runtime.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.shared_model[0].email}"
}

resource "google_cloud_run_v2_service" "shared_model" {
  count               = var.shared_model_image == null ? 0 : 1
  name                = "keplerops-model-${var.cell_id}"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = false
  labels              = local.labels

  scaling {
    scaling_mode          = "AUTOMATIC"
    min_instance_count    = 0
    manual_instance_count = 0
  }

  template {
    service_account                  = google_service_account.shared_model[0].email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    gpu_zonal_redundancy_disabled    = true
    max_instance_request_concurrency = var.shared_model_request_concurrency
    timeout                          = "60s"

    node_selector {
      accelerator = "nvidia-l4"
    }

    scaling {
      min_instance_count = var.shared_model_min_instances
      max_instance_count = var.shared_model_max_instances
    }

    containers {
      name  = "model"
      image = var.shared_model_image
      args = [
        "--model", "/models/teacher",
        "--served-model-name", "keplerops-teacher",
        "--host", "0.0.0.0",
        "--port", "8080",
      ]

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu              = "8"
          memory           = "32Gi"
          "nvidia.com/gpu" = "1"
        }
        cpu_idle          = false
        startup_cpu_boost = true
      }

      startup_probe {
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 24
        tcp_socket {
          port = 8080
        }
      }

      liveness_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 5
        period_seconds        = 30
        failure_threshold     = 3
        http_get {
          path = "/health"
          port = 8080
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository_iam_member.shared_model_reader,
    google_artifact_registry_repository.runtime,
    google_project_service.required,
  ]
}

resource "google_dns_managed_zone" "private_run" {
  count       = var.shared_model_image == null ? 0 : 1
  name        = "kep-${var.cell_id}-private-run"
  dns_name    = "run.app."
  description = "Private Google Access resolution for cell-internal Cloud Run inference."
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.cell.id
    }
  }
}

resource "google_dns_record_set" "private_run_apex" {
  count        = var.shared_model_image == null ? 0 : 1
  managed_zone = google_dns_managed_zone.private_run[0].name
  name         = "run.app."
  type         = "A"
  ttl          = 300
  rrdatas      = ["199.36.153.4", "199.36.153.5", "199.36.153.6", "199.36.153.7"]
}

resource "google_dns_record_set" "private_run_wildcard" {
  count        = var.shared_model_image == null ? 0 : 1
  managed_zone = google_dns_managed_zone.private_run[0].name
  name         = "*.run.app."
  type         = "A"
  ttl          = 300
  rrdatas      = ["199.36.153.4", "199.36.153.5", "199.36.153.6", "199.36.153.7"]
}

resource "google_storage_bucket" "cell_state" {
  name                        = "${var.project_id}-keplerops-${var.cell_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels
}

resource "google_compute_firewall" "participant_ingress" {
  name          = "kep-${var.cell_id}-participant"
  network       = google_compute_network.cell.name
  direction     = "INGRESS"
  priority      = 900
  source_ranges = var.participant_source_cidrs
  target_tags   = ["keplerops-participant"]
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
  log_config { metadata = "EXCLUDE_ALL_METADATA" }
}

resource "google_compute_firewall" "operator_iap" {
  name          = "kep-${var.cell_id}-iap"
  network       = google_compute_network.cell.name
  direction     = "INGRESS"
  priority      = 910
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["keplerops-range-host"]
  allow {
    protocol = "tcp"
    ports    = ["22", "3389"]
  }
  log_config { metadata = "EXCLUDE_ALL_METADATA" }
}

resource "google_compute_firewall" "range_overlay" {
  for_each      = var.range_subnets
  name          = "kep-${var.cell_id}-${each.key}-internal"
  network       = google_compute_network.cell.name
  direction     = "INGRESS"
  priority      = 920
  source_ranges = [each.value]
  target_tags   = ["keplerops-range-${each.key}"]
  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow { protocol = "icmp" }
  allow { protocol = "esp" }
  log_config { metadata = "EXCLUDE_ALL_METADATA" }
}

resource "google_compute_firewall" "range_overlay_egress" {
  name               = "kep-${var.cell_id}-overlay-egress"
  network            = google_compute_network.cell.name
  direction          = "EGRESS"
  priority           = 920
  destination_ranges = local.range_cidrs
  target_tags        = ["keplerops-range-host"]
  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow { protocol = "icmp" }
  allow { protocol = "esp" }
  log_config { metadata = "EXCLUDE_ALL_METADATA" }
}

resource "google_compute_firewall" "google_api_egress" {
  name               = "kep-${var.cell_id}-googleapi"
  network            = google_compute_network.cell.name
  direction          = "EGRESS"
  priority           = 1200
  destination_ranges = ["199.36.153.4/30"]
  target_tags        = ["keplerops-range-host"]
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
  log_config { metadata = "EXCLUDE_ALL_METADATA" }
}

resource "google_compute_firewall" "deny_egress" {
  name               = "kep-${var.cell_id}-deny-egress"
  network            = google_compute_network.cell.name
  direction          = "EGRESS"
  priority           = 65534
  destination_ranges = ["0.0.0.0/1", "128.0.0.0/1"]
  target_tags        = ["keplerops-range-host"]
  deny { protocol = "all" }
  log_config { metadata = "EXCLUDE_ALL_METADATA" }
}
