# OBS Bucket for File Archive Solution

provider "huaweicloud" {
  region = var.region
}

variable "bucket_name" {
  description = "OBS Bucket name for archive storage"
  type        = string
  default     = "my-archive-bucket"
}

variable "region" {
  description = "Huawei Cloud region"
  type        = string
  default     = "cn-north-4"
}

# Create OBS Bucket
resource "huaweicloud_obs_bucket" "archive" {
  bucket        = var.bucket_name
  storage_class = "STANDARD"
  multi_az      = true
  versioning    = true

  # Lifecycle policy
  lifecycle_rule {
    name    = "archive-cold"
    prefix  = "archive/"
    enabled = true
    transition {
      days          = 90
      storage_class = "COLD"
    }
    expiration {
      days = 365
    }
  }
}

# Output
output "bucket_name" {
  value = huaweicloud_obs_bucket.archive.bucket
}

output "bucket_region" {
  value = var.region
}
