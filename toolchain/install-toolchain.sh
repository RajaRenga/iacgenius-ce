#!/usr/bin/env bash
# IaC Genius CE deterministic toolchain. Pinned binaries, checksum-verified, plus a shared provider cache.
# Run on the instance (by the desk or the operator). The provider warm-up itself is the desk's `iacg onboard`
# task: once, confirm, reuse. This script only installs the binaries and creates the cache directory.
set -euo pipefail
TERRAFORM_VERSION="${IACG_TERRAFORM_VERSION:-1.15.9}"
TFLINT_VERSION="${IACG_TFLINT_VERSION:-0.64.0}"
CHECKOV_VERSION="${IACG_CHECKOV_VERSION:-3.3.16}"
CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-/data/iacg/plugins}"
command -v unzip >/dev/null || dnf install -y -q unzip
mkdir -p "$CACHE_DIR" /usr/local/bin
cd /tmp

curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip"
curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS"
grep " terraform_${TERRAFORM_VERSION}_linux_amd64.zip$" "terraform_${TERRAFORM_VERSION}_SHA256SUMS" | sha256sum -c -
unzip -o "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -d /usr/local/bin

curl -fsSLO "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_amd64.zip"
unzip -o tflint_linux_amd64.zip -d /usr/local/bin

# checkov in an isolated venv: AL2023 system python has rpm-managed packages pip cannot upgrade.
python3 -m venv /opt/iacg/venv
/opt/iacg/venv/bin/pip install --quiet --upgrade pip
/opt/iacg/venv/bin/pip install --quiet "checkov==${CHECKOV_VERSION}"
ln -sf /opt/iacg/venv/bin/checkov /usr/local/bin/checkov

printf 'export TF_PLUGIN_CACHE_DIR=%s\n' "$CACHE_DIR" >/etc/profile.d/iacg-cache.sh
echo "toolchain ready:"
terraform version
tflint --version
checkov --version
echo "provider cache: $CACHE_DIR (warm it once with 'iacg onboard', then reuse; registry off for init)"