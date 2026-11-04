output "edge_public_ip" {
  value = oci_core_instance.edge.public_ip
}

output "edge_private_ip" {
  value = oci_core_instance.edge.private_ip
}

output "worker_private_ip" {
  value = oci_core_instance.worker.private_ip
}
