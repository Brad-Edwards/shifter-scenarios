output "project_id" {
  description = "Existing project that contains the isolated range tenant."
  value       = var.project_id
}

output "participant_endpoint" {
  description = "Participant browser endpoint; not a credential or proof receipt."
  value = var.deploy_runtime ? format(
    "https://%s",
    google_compute_address.participant.address,
  ) : null
}

output "participant_address" {
  description = "Reserved participant endpoint address used for certificate binding."
  value       = google_compute_address.participant.address
}

output "runtime_repository" {
  description = "Cell-scoped Artifact Registry repository used by image publishing."
  value       = var.runtime_repository_id
}

output "shared_model_service_url" {
  description = "IAM-protected cell inference endpoint."
  value       = var.shared_model_service_url
}

output "range_zone" {
  description = "Zone containing the tenant runtime nodes."
  value       = var.zone
}

output "asset_inventory" {
  description = "Logical-to-physical inventory for the packed nested range."
  value = var.deploy_runtime ? {
    for host_id in keys(local.physical_hosts) : host_id => {
      name        = google_compute_instance.range_host[0].name
      internal_ip = local.physical_host_ips[host_id]
      status      = google_compute_instance.range_host[0].current_status
    }
  } : {}
}

output "outer_host_count" {
  description = "Physical Compute Engine instances consumed by one range."
  value       = var.deploy_runtime ? length(google_compute_instance.range_host) : 0
}

output "nested_windows_guest_count" {
  description = "Windows guests materialized under nested KVM."
  value       = var.deploy_runtime ? length(google_compute_disk.windows_guest) : 0
}
