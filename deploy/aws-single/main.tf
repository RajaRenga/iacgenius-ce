# IaC Genius Community Edition on one Spot instance.
# Borrows the RemediGenius-CE aws-single patterns: disposable instance, private S3 state,
# SSM-only access, pinned Hermes image, IMDSv2 hop limit 1, model key from Secrets Manager.
# The iacg desk is built on the instance by Hermes; generation needs no AWS read credentials.
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.68"
    }
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags {
    tags = {
      Project = "iacgenius-ce", Stack = var.name, ManagedBy = "terraform"
    }
  }
}

variable "account_id" {
  type = string
}
variable "subnet_id" {
  type        = string
  description = "Existing subnet with outbound HTTPS (public with an internet gateway, or private with NAT)."
}
variable "region" {
  type    = string
  default = "us-east-1"
}
variable "name" {
  type    = string
  default = "iacgenius-ce"
}
variable "source_zip" {
  type        = string
  description = "Package from tools/package_release.py --spot."
}
variable "running" {
  type    = bool
  default = true
}
variable "model_secret_arn" {
  type        = string
  default     = ""
  description = "Existing Secrets Manager secret holding only the model API key."
}
variable "model_name" {
  type    = string
  default = "deepseek-v4.1-flash"
}
variable "model_base_url" {
  type        = string
  default     = ""
  description = "OpenAI-compatible endpoint for model_name. Required when model_secret_arn is set."
}
variable "public_ip" {
  type    = bool
  default = true
}
variable "spot_instance_types" {
  type    = list(string)
  default = ["t3.large", "t3a.large"]
}
variable "container_memory_mb" {
  type    = number
  default = 6144
  validation {
    condition     = var.container_memory_mb >= 1024 && var.container_memory_mb <= 131072
    error_message = "Choose a memory limit from 1024 to 131072 MiB that fits your instance."
  }
}
variable "delete_data_on_destroy" {
  type    = bool
  default = false
}

check "model_endpoint" {
  assert {
    condition     = var.model_secret_arn == "" || var.model_base_url != ""
    error_message = "Set model_base_url (OpenAI-compatible endpoint) when model_secret_arn is set."
  }
}

data "aws_subnet" "selected" {
  id = var.subnet_id
}
data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_s3_bucket" "data" {
  bucket_prefix = "${var.name}-"
  force_destroy = var.delete_data_on_destroy
}
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "expire-old-checkpoint-versions"
    status = "Enabled"
    filter {
      prefix = "state/"
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  bucket = aws_s3_bucket.data.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } }] })
}
resource "aws_s3_object" "source" {
  bucket      = aws_s3_bucket.data.id
  key         = "source/iacgenius-ce.zip"
  source      = var.source_zip
  source_hash = filesha256(var.source_zip)
}

resource "aws_security_group" "host" {
  name_prefix = "${var.name}-"
  vpc_id      = data.aws_subnet.selected.vpc_id
  description = "IaC Genius CE: SSM only, no inbound rules"
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

locals {
  config = {
    name                = var.name, region = var.region, account_id = var.account_id, bucket = aws_s3_bucket.data.id,
    archive_key         = aws_s3_object.source.key, archive_sha256 = filesha256(var.source_zip),
    model_secret        = var.model_secret_arn, model_name = var.model_name, model_base_url = var.model_base_url,
    container_memory_mb = var.container_memory_mb,
    image               = "nousresearch/hermes-agent:v0.23.1@sha256:276d44685c65c0cb2a25f190b63c65c8906f9dc76486fb1c05ae71b5826bda08"
  }
}

resource "aws_launch_template" "host" {
  name_prefix   = "${var.name}-"
  image_id      = data.aws_ssm_parameter.ami.value
  instance_type = var.spot_instance_types[0]
  iam_instance_profile {
    name = aws_iam_instance_profile.host.name
  }
  network_interfaces {
    associate_public_ip_address = var.public_ip
    security_groups             = [aws_security_group.host.id]
  }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }
  user_data = base64encode(templatefile("${path.module}/user-data.sh.tftpl", { config_b64 = base64encode(jsonencode(local.config)) }))
  tag_specifications {
    resource_type = "instance"
    tags          = { Name = var.name }
  }
  tag_specifications {
    resource_type = "volume"
    tags          = { Name = var.name }
  }
}

resource "aws_autoscaling_group" "host" {
  name                = var.name
  min_size            = 0
  max_size            = 1
  desired_capacity    = var.running ? 1 : 0
  vpc_zone_identifier = [var.subnet_id]
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 0
      spot_allocation_strategy                 = "price-capacity-optimized"
    }
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.host.id
        version            = aws_launch_template.host.latest_version
      }
      dynamic "override" {
        for_each = var.spot_instance_types
        content {
          instance_type = override.value
        }
      }
    }
  }
  depends_on = [aws_iam_role_policy.host, aws_iam_role_policy_attachment.ssm, aws_s3_bucket_public_access_block.data, aws_s3_bucket_versioning.data]
}

output "bucket" {
  value = aws_s3_bucket.data.id
}
output "autoscaling_group" {
  value = aws_autoscaling_group.host.name
}
output "instance_role" {
  value = aws_iam_role.host.arn
}
output "data_notice" {
  description = "Read before first use."
  value       = "IaC Genius CE runs on Hermes with the model provider you configure. Requests, IaC excerpts and chat are sent to that provider; CE runs no model of its own. One operator per installation. Model endpoint: ${var.model_base_url == "" ? "set in the dashboard" : var.model_base_url}"
}