#------------------------------------------------------------------------------
# POLARIS test range — N parallel ranges inside a dedicated range VPC,
# each one an Ubuntu polaris VM running the docker-compose stack plus a
# Windows Server 2022 DC for BOREAS.LOCAL. Every range lives in its own
# /28 subnet with pinned private IPs (.10 polaris, .11 DC) so compose zone
# files and the a2_setup.ps1 contract work unchanged for any N.
#
# The VPC, internet gateway, build-artifact bucket, IAM role, and instance
# profile are created with the range. No portal VPC, peering, NAT gateway,
# pre-baked AMI, or external artifact bucket is required.
#
# Per-range resources live in ranges.tf and use for_each on
# var.range_indices so each index gets its own subnet/route table/instance
# pair without resource-address drift on apply.
#
# This is a manual "user range" — cyberscript/provisioner is bypassed; DB
# records are populated by polaris/aws-range/register_range.py once
# the VMs are up.
#------------------------------------------------------------------------------

locals {
  name_prefix = var.range_id

  # Per-range subnet + IP plan. For each range index, carve a /28 out of
  # var.polaris_cidr_block and pin polaris .10 / a2 .11 inside it.
  range_subnets = {
    for idx in var.range_indices : idx => {
      cidr       = cidrsubnet(var.polaris_cidr_block, 4, tonumber(idx))
      polaris_ip = cidrhost(cidrsubnet(var.polaris_cidr_block, 4, tonumber(idx)), 10)
      a2_ip      = cidrhost(cidrsubnet(var.polaris_cidr_block, 4, tonumber(idx)), 11)
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_vpc" "polaris" {
  cidr_block           = var.polaris_cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}

resource "aws_internet_gateway" "polaris" {
  vpc_id = aws_vpc.polaris.id

  tags = {
    Name = "${local.name_prefix}-igw"
  }
}

resource "aws_s3_bucket" "build" { # NOSONAR -- ephemeral, force-destroyed rehearsal artifact bucket
  bucket        = "${var.range_id}-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name = "${local.name_prefix}-build"
  }
}

resource "aws_s3_bucket_policy" "build_https_only" {
  bucket = aws_s3_bucket.build.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.build.arn,
        "${aws_s3_bucket.build.arn}/*",
      ]
      Condition = {
        Bool = {
          "aws:SecureTransport" = "false"
        }
      }
    }]
  })
}

resource "aws_s3_bucket_public_access_block" "build" {
  bucket = aws_s3_bucket.build.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "build" {
  bucket = aws_s3_bucket.build.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_object" "build" {
  bucket = aws_s3_bucket.build.id
  key    = "polaris/build-v1.tar.gz"
  source = "${path.module}/../build/build-v1.tar.gz"
  etag   = filemd5("${path.module}/../build/build-v1.tar.gz")

  depends_on = [
    aws_s3_bucket_public_access_block.build,
    aws_s3_bucket_policy.build_https_only,
    aws_s3_bucket_server_side_encryption_configuration.build,
  ]
}
