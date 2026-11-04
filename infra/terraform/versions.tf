terraform {
  required_version = ">= 1.5"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
  }
  # State stays local and git-ignored (see .gitignore). Move to OCI Object Storage
  # (S3-compatible backend) once a second machine needs to run plan/apply.
}

provider "oci" {
  config_file_profile = var.oci_profile
  region              = var.region
}
