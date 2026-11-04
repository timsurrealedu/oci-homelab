# VCN "lifeos" was built with the console's VCN wizard (2026-06-30) and imported.
# Layout: public 10.0.0.0/24 (IGW) for edge, private 10.0.1.0/24 (NAT GW + service GW) for worker.
# Oracle-managed defined tags and the wizard's freeform tags are left alone.

locals {
  compartment_id = var.tenancy_ocid
  vcn_cidr       = "10.0.0.0/16"
  public_cidr    = "10.0.0.0/24"
  private_cidr   = "10.0.1.0/24"
  tags           = { project = "oci-homelab", managed-by = "terraform" }
}

resource "oci_core_vcn" "main" {
  compartment_id = local.compartment_id
  cidr_blocks    = [local.vcn_cidr]
  display_name   = "lifeos"
  dns_label      = "lifeos"

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

resource "oci_core_internet_gateway" "main" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "Internet gateway-lifeos"
  enabled        = true

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

resource "oci_core_nat_gateway" "main" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "NAT gateway-lifeos"
  block_traffic  = false

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

data "oci_core_services" "all" {
  filter {
    name   = "name"
    values = ["All .* Services In Oracle Services Network"]
    regex  = true
  }
}

resource "oci_core_service_gateway" "main" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "Service gateway-lifeos"

  services {
    service_id = data.oci_core_services.all.services[0].id
  }

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

resource "oci_core_default_route_table" "public" {
  manage_default_resource_id = oci_core_vcn.main.default_route_table_id
  display_name               = "default route table for lifeos"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main.id
  }

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

resource "oci_core_route_table" "private" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "route table for private private subnet-lifeos"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.main.id
  }

  route_rules {
    destination       = data.oci_core_services.all.services[0].cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.main.id
  }

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

# Subnet-wide baseline: SSH + path-MTU ICMP only. Service ports live in the NSGs (nsg.tf).
resource "oci_core_default_security_list" "public" {
  manage_default_resource_id = oci_core_vcn.main.default_security_list_id
  display_name               = "Default Security List for lifeos"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # Break-glass SSH (keys only). Planned: Tailscale-only once Phase 2 hardening is proven.
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Port 80 moved to nsg-edge (2026-11, Phase 1).

  ingress_security_rules {
    protocol = "1"
    source   = "0.0.0.0/0"
    icmp_options {
      type = 3
      code = 4
    }
  }

  ingress_security_rules {
    protocol = "1"
    source   = local.vcn_cidr
    icmp_options {
      type = 3
    }
  }

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

resource "oci_core_security_list" "private" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "security list for private subnet-lifeos"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    protocol = "6"
    source   = local.vcn_cidr
    tcp_options {
      min = 22
      max = 22
    }
  }

  ingress_security_rules {
    protocol = "1"
    source   = "0.0.0.0/0"
    icmp_options {
      type = 3
      code = 4
    }
  }

  ingress_security_rules {
    protocol = "1"
    source   = local.vcn_cidr
    icmp_options {
      type = 3
    }
  }

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = local.compartment_id
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = local.public_cidr
  display_name               = "public subnet-lifeos"
  dns_label                  = "sub06300629100"
  prohibit_public_ip_on_vnic = false
  route_table_id             = oci_core_default_route_table.public.id
  security_list_ids          = [oci_core_default_security_list.public.id]
  dhcp_options_id            = oci_core_vcn.main.default_dhcp_options_id

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}

resource "oci_core_subnet" "private" {
  compartment_id             = local.compartment_id
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = local.private_cidr
  display_name               = "private subnet-lifeos"
  dns_label                  = "sub06300629101"
  prohibit_public_ip_on_vnic = true
  route_table_id             = oci_core_route_table.private.id
  security_list_ids          = [oci_core_security_list.private.id]
  dhcp_options_id            = oci_core_vcn.main.default_dhcp_options_id

  lifecycle {
    ignore_changes = [defined_tags, freeform_tags]
  }
}
