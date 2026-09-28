data "google_compute_network" "keplerops" {
  name    = "cinder-keplerops-golden"
  project = var.project_id
}

data "google_compute_network" "arwc" {
  name    = "cinder-arwc-golden"
  project = var.project_id
}

resource "google_compute_network_peering" "keplerops_to_arwc" {
  name                 = "cinder-keplerops-to-arwc"
  network              = data.google_compute_network.keplerops.self_link
  peer_network         = data.google_compute_network.arwc.self_link
  export_custom_routes = false
  import_custom_routes = false
}

resource "google_compute_network_peering" "arwc_to_keplerops" {
  name                 = "cinder-arwc-to-keplerops"
  network              = data.google_compute_network.arwc.self_link
  peer_network         = data.google_compute_network.keplerops.self_link
  export_custom_routes = false
  import_custom_routes = false
}

resource "google_compute_firewall" "arwc_fieldlink_consumer" {
  name          = "cinder-arwc-fieldlink-from-keplerops"
  project       = var.project_id
  network       = data.google_compute_network.arwc.name
  direction     = "INGRESS"
  priority      = 800
  source_ranges = ["10.77.49.2/32"]
  target_tags   = ["cinder-arwc-carrier"]

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  log_config {
    metadata = "EXCLUDE_ALL_METADATA"
  }
}
