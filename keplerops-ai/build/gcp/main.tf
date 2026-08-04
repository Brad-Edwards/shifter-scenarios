locals {
  suffix = substr(sha256("${var.range_instance}:${var.participant}"), 0, 6)
  range_subnet_key = element(
    reverse(split("-", element(reverse(split("/", var.range_subnet_self_link)), 0))),
    0,
  )
  labels = {
    scenario     = "keplerops-ai"
    profile      = "gcp-full"
    "managed-by" = "shifter-scenarios"
    range        = var.range_instance
    participant  = var.participant
  }
  sdl_realization  = jsondecode(file(var.sdl_realization_file))
  company_state    = yamldecode(file("${path.module}/../../assets/content/company-state/company-state.yaml"))
  logical_networks = local.sdl_realization.logical_networks
  workloads        = local.sdl_realization.workloads
  physical_hosts   = local.sdl_realization.physical_hosts
  placements       = local.sdl_realization.placements
  declared_routes  = local.sdl_realization.declared_routes
  range_workloads = {
    for workload_id, workload in local.workloads : workload_id => workload
    if workload.deployment_cell == "range-cell"
  }
  nested_windows_hosts = {
    for host_id, host in local.physical_hosts : host_id => host
    if host.os == "windows"
  }
  nested_guest_ips = {
    "ad-dc-01"                 = "192.168.77.10"
    "workforce-workstation-01" = "192.168.77.11"
    "ml-workstation-01"        = "192.168.77.12"
  }
  outer_host_ip = cidrhost(var.range_subnet_cidr, var.range_host_ip_offset)
  physical_host_ips = {
    for host_id in keys(local.physical_hosts) :
    host_id => lookup(local.nested_guest_ips, host_id, local.outer_host_ip)
  }
  image_lock = jsondecode(
    var.deploy_runtime ? file(var.image_lock_file) : jsonencode({ images = {}, auxiliary_images = {} })
  )
  runtime_secret_ids = toset(local.sdl_realization.runtime_secret_ids)
  evidence_producers = toset(local.sdl_realization.evidence_producers)
  secret_access = toset([
    for binding in local.sdl_realization.secret_access : binding
  ])
  nested_secret_access = {
    for host_id in keys(local.nested_windows_hosts) : host_id => sort([
      for binding in local.secret_access : split("/", binding)[1]
      if split("/", binding)[0] == host_id
    ])
  }
  packed_workload_plan = {
    for workload_id, workload in local.range_workloads : workload_id => merge(workload, {
      image = var.deploy_runtime ? format(
        "%s@%s",
        local.image_lock.images[workload.component].uri,
        local.image_lock.images[workload.component].digest,
      ) : ""
    })
  }
  host_workload_plans = {
    "range-linux-carrier-01" = local.packed_workload_plan
  }
}

data "google_project" "target" {
  provider   = google.range
  project_id = var.project_id
}

resource "google_project_service" "required" {
  provider = google.range
  for_each = toset([
    "compute.googleapis.com",
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

resource "google_compute_address" "participant" {
  provider     = google.range
  name         = "keplerops-participant-${local.suffix}"
  region       = var.region
  address_type = "EXTERNAL"
  network_tier = "PREMIUM"
  depends_on   = [google_project_service.required]
}

resource "google_storage_bucket" "workspace" {
  provider                    = google.range
  name                        = "${var.project_id}-keplerops-workspaces-${local.suffix}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  labels                      = local.labels

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 1
    }
  }
}

resource "google_service_account" "range_host" {
  provider     = google.range
  account_id   = substr("kep-rangehost-${local.suffix}", 0, 30)
  display_name = "KeplerOps packed range host"
  description  = "Keyless identity for the packed nested KeplerOps range"
}

resource "google_secret_manager_secret" "runtime" {
  provider  = google.range
  for_each  = local.runtime_secret_ids
  secret_id = "kep-${replace(each.key, "-", "")}-${local.suffix}"
  labels    = local.labels
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "overlay_join" {
  provider  = google.range
  count     = var.deploy_runtime ? 1 : 0
  secret_id = "kep-overlay-${local.suffix}"
  labels    = local.labels
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "range_host" {
  provider  = google.range
  for_each  = local.runtime_secret_ids
  project   = var.project_id
  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_secret_manager_secret_iam_member" "overlay_reader" {
  provider  = google.range
  count     = var.deploy_runtime ? 1 : 0
  project   = var.project_id
  secret_id = google_secret_manager_secret.overlay_join[0].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_secret_manager_secret_iam_member" "overlay_writer" {
  provider  = google.range
  count     = var.deploy_runtime ? 1 : 0
  project   = var.project_id
  secret_id = google_secret_manager_secret.overlay_join[0].secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_artifact_registry_repository_iam_member" "reader" {
  provider   = google.range
  location   = var.runtime_repository_location
  repository = var.runtime_repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_cloud_run_v2_service_iam_member" "model_invoker" {
  provider = google.range
  project  = var.project_id
  location = var.region
  name     = var.shared_model_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_project_iam_member" "log_writer" {
  provider = google.range
  project  = var.project_id
  role     = "roles/logging.logWriter"
  member   = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_project_iam_member" "range_ops_run_developer" {
  provider = google.range
  project  = var.project_id
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_service_account_iam_member" "range_ops_self_user" {
  provider           = google.range
  service_account_id = google_service_account.range_host.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_storage_bucket_iam_member" "range_ops_workspace_admin" {
  provider = google.range
  bucket   = google_storage_bucket.workspace.name
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${google_service_account.range_host.email}"
}

resource "google_compute_disk" "windows_guest" {
  provider = google.range
  for_each = var.deploy_runtime ? local.nested_windows_hosts : {}
  name     = "kep-${replace(each.key, "-", "")}-${local.suffix}"
  type     = "pd-balanced"
  zone     = var.zone
  image    = var.windows_image
  size     = each.value.disk_gib
  labels   = merge(local.labels, { guest = each.key })
}

resource "google_compute_instance" "range_host" {
  provider     = google.range
  count        = var.deploy_runtime ? 1 : 0
  name         = "kep-rangehost-${local.suffix}"
  machine_type = var.nested_host_machine_type
  zone         = var.zone
  tags = [
    "keplerops-range-host",
    "keplerops-participant",
    "keplerops-range-${var.range_instance}",
    "keplerops-range-${local.range_subnet_key}",
  ]
  labels = merge(local.labels, { host = "packed-nested-range" })

  boot_disk {
    auto_delete = true
    initialize_params {
      image = var.nested_host_image
      size  = var.nested_host_disk_gib
      type  = "pd-balanced"
    }
  }

  dynamic "attached_disk" {
    for_each = google_compute_disk.windows_guest
    content {
      source      = attached_disk.value.self_link
      device_name = "kep-${attached_disk.key}"
      mode        = "READ_WRITE"
    }
  }

  advanced_machine_features {
    enable_nested_virtualization = true
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    provisioning_model  = "STANDARD"
  }

  network_interface {
    subnetwork = var.range_subnet_self_link
    network_ip = local.outer_host_ip
    access_config {
      nat_ip       = google_compute_address.participant.address
      network_tier = "PREMIUM"
    }
  }

  service_account {
    email  = google_service_account.range_host.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata = {
    block-project-ssh-keys              = "true"
    enable-guest-attributes             = "true"
    enable-oslogin                      = "true"
    serial-port-enable                  = "false"
    startup-script                      = file("${path.module}/outer-bootstrap.sh")
    keplerops-nested-bootstrap          = file("${path.module}/nested-bootstrap.sh")
    keplerops-nested-metadata           = file("${path.module}/nested-metadata.py")
    keplerops-nested-secret-access      = jsonencode(local.nested_secret_access)
    keplerops-workload-bootstrap        = file("${path.module}/workload-bootstrap.sh")
    keplerops-carrier-bootstrap         = file("${path.module}/carrier-bootstrap.sh")
    keplerops-host-id                   = "range-linux-carrier-01"
    keplerops-range-instance            = var.range_instance
    keplerops-participant               = var.participant
    keplerops-region                    = var.region
    keplerops-project-id                = var.project_id
    keplerops-secret-suffix             = local.suffix
    keplerops-logical-networks          = jsonencode(local.logical_networks)
    keplerops-workload-plan             = jsonencode(local.packed_workload_plan)
    keplerops-all-workload-plans        = jsonencode(local.host_workload_plans)
    keplerops-declared-routes           = jsonencode(local.declared_routes)
    keplerops-physical-host-ips         = jsonencode(local.physical_host_ips)
    keplerops-image-lock                = jsonencode(local.image_lock)
    keplerops-evidence-producers        = join(" ", local.sdl_realization.evidence_producers)
    keplerops-research-capture-signals  = jsonencode(var.telemetry_capture_signals)
    keplerops-workspace-bucket-name     = google_storage_bucket.workspace.name
    keplerops-overlay-token-secret      = google_secret_manager_secret.overlay_join[0].secret_id
    keplerops-range-ops-service-account = google_service_account.range_host.email
    keplerops-shared-model-url          = var.shared_model_service_url
    keplerops-windows-bootstrap-ad-dc-01 = templatefile(
      "${path.module}/windows-bootstrap.ps1.tpl",
      {
        host_id           = "ad-dc-01"
        range_instance    = var.range_instance
        ad_domain_dns     = "keplerops.test"
        ad_domain_netbios = "KEPLEROPS"
        ad_controller_ip  = local.nested_guest_ips["ad-dc-01"]
        company_state_b64 = base64encode(jsonencode(local.company_state))
        secret_suffix     = local.suffix
        project_id        = var.project_id
        nested_bridge_url = "http://192.168.77.1:8080"
      },
    )
    keplerops-windows-bootstrap-workforce-workstation-01 = templatefile(
      "${path.module}/windows-bootstrap.ps1.tpl",
      {
        host_id           = "workforce-workstation-01"
        range_instance    = var.range_instance
        ad_domain_dns     = "keplerops.test"
        ad_domain_netbios = "KEPLEROPS"
        ad_controller_ip  = local.nested_guest_ips["ad-dc-01"]
        company_state_b64 = base64encode(jsonencode(local.company_state))
        secret_suffix     = local.suffix
        project_id        = var.project_id
        nested_bridge_url = "http://192.168.77.1:8080"
      },
    )
    keplerops-windows-bootstrap-ml-workstation-01 = templatefile(
      "${path.module}/windows-bootstrap.ps1.tpl",
      {
        host_id           = "ml-workstation-01"
        range_instance    = var.range_instance
        ad_domain_dns     = "keplerops.test"
        ad_domain_netbios = "KEPLEROPS"
        ad_controller_ip  = local.nested_guest_ips["ad-dc-01"]
        company_state_b64 = base64encode(jsonencode(local.company_state))
        secret_suffix     = local.suffix
        project_id        = var.project_id
        nested_bridge_url = "http://192.168.77.1:8080"
      },
    )
  }

  shielded_instance_config {
    enable_secure_boot          = false
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  allow_stopping_for_update = false
  deletion_protection       = false
  depends_on = [
    google_artifact_registry_repository_iam_member.reader,
    google_cloud_run_v2_service_iam_member.model_invoker,
    google_project_iam_member.range_ops_run_developer,
    google_secret_manager_secret_iam_member.overlay_reader,
    google_secret_manager_secret_iam_member.overlay_writer,
    google_secret_manager_secret_iam_member.range_host,
    google_service_account_iam_member.range_ops_self_user,
    google_storage_bucket_iam_member.range_ops_workspace_admin,
  ]
}
