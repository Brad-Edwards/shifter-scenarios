output "keplerops_network" {
  value = data.google_compute_network.keplerops.name
}

output "arwc_network" {
  value = data.google_compute_network.arwc.name
}

output "allowed_flow" {
  value = "10.77.49.2 -> 10.77.59.2 tcp/443"
}
