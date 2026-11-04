# Instance-level rules. Security lists keep only the subnet baseline (SSH + ICMP).
resource "oci_core_network_security_group" "edge" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "nsg-edge"
  freeform_tags  = local.tags
}

# Public HTTP to Caddy. 443 (Caddy) and 53 (interactsh) get added in Phases 3-4, when something listens.
resource "oci_core_network_security_group_security_rule" "edge_http" {
  network_security_group_id = oci_core_network_security_group.edge.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  description               = "HTTP to Caddy"
  tcp_options {
    destination_port_range {
      min = 80
      max = 80
    }
  }
}

resource "oci_core_network_security_group" "worker" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "nsg-worker"
  freeform_tags  = local.tags
}

# Only the edge may reach the worker: SSH (Ansible), HTTP/HTTPS (Caddy -> app proxy), node exporter.
resource "oci_core_network_security_group_security_rule" "worker_from_edge" {
  for_each = { ssh = 22, http = 80, https = 443, node-exporter = 9100 }

  network_security_group_id = oci_core_network_security_group.worker.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = oci_core_network_security_group.edge.id
  source_type               = "NETWORK_SECURITY_GROUP"
  description               = "${each.key} from edge"
  tcp_options {
    destination_port_range {
      min = each.value
      max = each.value
    }
  }
}
