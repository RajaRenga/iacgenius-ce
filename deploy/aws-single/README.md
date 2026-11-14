# IaC Genius CE on one AWS Spot instance

A disposable Spot instance in an Auto Scaling group, a private S3 bucket for the Hermes home checkpoints, and
SSM-only access (no inbound port). Borrows the RemediGenius-CE `aws-single` patterns. If AWS reclaims the
instance, the group launches a new one and it restores the Hermes home from S3.

## Before you begin
- Terraform >= 1.10, AWS CLI v2 with the Session Manager plugin, Python 3.11+.
- A provisioning identity that can create IAM roles, an S3 bucket, a security group, a launch template and an ASG.
- An existing subnet with outbound HTTPS. Your model API key in Secrets Manager as a plain string.

## Deploy
```sh
python tools/package_release.py --spot dist/iacgenius-ce-spot.zip
cd deploy/aws-single
cp example.tfvars local.tfvars        # set account_id, subnet_id, source_zip, model_*
terraform init
terraform plan -var-file=local.tfvars
terraform apply -var-file=local.tfvars
```

First boot installs docker, pulls the pinned Hermes image, restores the Hermes home, seeds the model and starts
the gateway. Then open the dashboard over SSM and tell Hermes to read `BUILD-BRIEF.md` and start building.

## Open the dashboard
SSM port-forward to `http://127.0.0.1:9126`. The login is in `/data/hermes/iacgenius-login.json` on the instance.

## Stop, start, remove
- Stop: `running = false` and apply (scale to zero). State stays in S3. Start: `running = true`.
- Remove: `terraform destroy`. The bucket is kept unless `delete_data_on_destroy = true`.

## On the instance
- `iacgenius-hermes.service` — the pinned Hermes container, profile `iacgenius`, no AWS credentials.
- `iacgenius-checkpoint.timer` — checkpoints the Hermes home to S3 every 2 minutes.
- The iacg desk, plugin, board and toolchain are built on the instance from `BUILD-BRIEF.md`.