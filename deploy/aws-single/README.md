# IaC Genius CE on one AWS instance

One EC2 instance in an Auto Scaling group, a private S3 bucket for state, and SSM-only access (no inbound
port). Borrows the RemediGenius-CE `aws-single` patterns.

**Use a persistent (on-demand) EC2 instance for the Community Edition.** A Spot instance can be reclaimed
by AWS at any time, and anything not mirrored to S3 is lost with it. The maintainer lab runs on Spot to
save cost and relies on the optional incremental S3 sync below; for your own CE, prefer on-demand so your
work is not interrupted. If you do choose Spot, enable `s3_sync` so state survives a reclaim.

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
- `iacgenius-checkpoint.timer` — mirrors state to S3 (see below).
- The iacg desk, plugin, board and toolchain are built on the instance from `BUILD-BRIEF.md`.

## State durability (optional incremental S3 sync)

The filesystem is the source of truth: a mission is its folder under `/data/iacg-work` (the `.tf` code plus
a `work/` provenance folder). A mission whose folder is gone is forgotten, not kept as a stale record.

By default a lightweight checkpoint tars the Hermes home + desk DB to S3 every 2 minutes. **For durable,
incremental mirroring of the actual work, set `s3_sync = true`** in the instance `config.json`
(`/opt/iacgenius/config.json`) and re-run `host.py`. This switches the checkpoint to `aws s3 sync`, which
transfers **only changed files** (unchanged files are never re-transmitted), every **5 minutes**:

- `/data/iacg-work` → `s3://<bucket>/live/work/` (mission folders; provider binaries and zips excluded)
- `/data/iacg` → `s3://<bucket>/live/iacg/` (desk DB, knowledge, schema cache; provider cache excluded)
- `/data/hermes/profiles` → `s3://<bucket>/live/profiles/` (the profile and skills)

On boot, `host.py` syncs these back down, so a replacement instance recovers what was there. Enable this if
you run on Spot, or want your work to survive an instance change. The bucket's IAM role needs `s3:ListBucket`,
`s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on the bucket (sync `--delete` mirrors removals).

To force a sync now: `systemctl start iacgenius-checkpoint.service`. The timer cadence is 5 minutes with
sync enabled (2 minutes for the legacy checkpoint).