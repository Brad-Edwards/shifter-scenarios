output "cell_id" {
  value = var.cell_id
}

output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "network_self_link" {
  value = google_compute_network.cell.self_link
}

output "range_subnet_self_links" {
  value = {
    for range_id, subnet in google_compute_subnetwork.range :
    range_id => subnet.self_link
  }
}

output "runtime_repository" {
  value = google_artifact_registry_repository.runtime.repository_id
}

output "shared_model_service_name" {
  description = "Cell-owned Cloud Run service name; null until a digest-pinned model image is activated."
  value       = one(google_cloud_run_v2_service.shared_model[*].name)
}

output "shared_model_service_url" {
  description = "IAM-protected internal inference URL and identity-token audience."
  value       = one(google_cloud_run_v2_service.shared_model[*].uri)
}

output "cell_state_bucket" {
  value = google_storage_bucket.cell_state.name
}
