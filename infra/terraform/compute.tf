# edge = the original "newLifeOS" instance (created 2026-07-02), imported. Never recreate it:
# ap-batam-1 A1 capacity is scarce. Shape changes are applied in place (reboot).
resource "oci_core_instance" "edge" {
  compartment_id      = local.compartment_id
  availability_domain = var.availability_domain
  fault_domain        = "FAULT-DOMAIN-3"
  display_name        = "newLifeOS"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.edge_ocpus
    memory_in_gbs = var.edge_memory_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = "true"
    hostname_label   = "instance-20260702-1842"
    display_name     = "instance-20260702-1842"
    private_ip       = "10.0.0.165"
    nsg_ids          = [oci_core_network_security_group.edge.id]
  }

  source_details {
    source_type = "image"
    source_id   = "ocid1.image.oc1.ap-batam-1.aaaaaaaa2mt3zn5aygyi3xdcjk2dseruubi5tnyxcj3qpdpx45mrth735kba"
  }

  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }

  lifecycle {
    prevent_destroy = true
    # SSH keys are managed on the host (Ansible); image/boot details and VNIC tags are launch-time only.
    ignore_changes = [defined_tags, metadata, source_details, create_vnic_details[0].defined_tags, agent_config]
  }
}

# worker: private subnet, no public IP. Egress via NAT gateway; reachable only from edge and Tailscale.
resource "oci_core_instance" "worker" {
  compartment_id      = local.compartment_id
  availability_domain = var.availability_domain
  display_name        = "worker"
  shape               = "VM.Standard.A1.Flex"
  freeform_tags       = local.tags

  shape_config {
    ocpus         = var.worker_ocpus
    memory_in_gbs = var.worker_memory_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.private.id
    assign_public_ip = "false"
    hostname_label   = "worker"
    private_ip       = "10.0.1.10"
    nsg_ids          = [oci_core_network_security_group.worker.id]
  }

  source_details {
    source_type             = "image"
    source_id               = var.worker_image_id
    boot_volume_size_in_gbs = 50
  }

  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }

  metadata = {
    ssh_authorized_keys = join("\n", [for f in fileset("${path.module}/keys", "*.pub") : trimspace(file("${path.module}/keys/${f}"))])
    user_data           = base64encode(templatefile("${path.module}/cloud-init/worker.yaml.tftpl", { ts_authkey = var.tailscale_authkey }))
  }

  # The A1 budget is shared: edge must shrink before the worker can exist.
  depends_on = [oci_core_instance.edge]

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [defined_tags, metadata, source_details[0].source_id, create_vnic_details[0].defined_tags]
  }
}
