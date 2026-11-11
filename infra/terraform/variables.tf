variable "oci_profile" {
  type    = string
  default = "DEFAULT"
}

variable "region" {
  type    = string
  default = "ap-batam-1"
}

variable "tenancy_ocid" {
  description = "Root compartment; everything lives there."
  type        = string
  default     = "ocid1.tenancy.oc1..aaaaaaaaogubn5zhyu4turprxmsy3ivmrilxgkthxaty4ysxjrvmhuraxlia"
}

variable "availability_domain" {
  type    = string
  default = "sjag:AP-BATAM-1-AD-1"
}

# Always Free A1 budget: 2 OCPU / 12 GB total across all A1 instances.
variable "edge_ocpus" {
  type    = number
  default = 1
}

variable "edge_memory_gbs" {
  type    = number
  default = 6
}

variable "worker_ocpus" {
  type    = number
  default = 1
}

variable "worker_memory_gbs" {
  type    = number
  default = 6
}

variable "worker_image_id" {
  description = "Canonical-Ubuntu-24.04-aarch64-2026.10.27-0 (pinned; launch-time only)."
  type        = string
  default     = "ocid1.image.oc1.ap-batam-1.aaaaaaaapeavfbdxgxzn2nvvjlmvbr2pxan2tf5jurb734jau7o2d4n7tuuq"
}

variable "tailscale_authkey" {
  description = "Optional one-off, pre-authorized, tagged (tag:worker) Tailscale key. Ends up in instance metadata and state, so use a single-use key. Empty = join later over SSH from edge."
  type        = string
  default     = ""
  sensitive   = true
}

variable "edge_public_web" {
  description = "Open 443 on nsg-edge for public Caddy sites (set true when going public)."
  type        = bool
  default     = false
}
