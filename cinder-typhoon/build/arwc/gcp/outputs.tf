output "instance_name" {
  value = google_compute_instance.carrier.name
}

output "zone" {
  value = google_compute_instance.carrier.zone
}

output "private_ip" {
  value = google_compute_instance.carrier.network_interface[0].network_ip
}

output "operator_entry" {
  value = "gcloud compute ssh ${google_compute_instance.carrier.name} --project ${var.project_id} --zone ${var.zone} --tunnel-through-iap"
}
