terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "polaris"
      ManagedBy = "terraform"
      Purpose   = "golden-range-bake"
      RangeId   = var.range_id
    }
  }
}
