#!/usr/bin/env bash
# Read-only Terraform Registry capability for IaC Genius CE.
# Reuses the official HashiCorp MCP binary and Hermes configuration; no provider API client, no credentials.
# Adapted from the RemediGenius-CE installer. NOT the deprecated awslabs terraform-mcp-server.
set -euo pipefail
IMAGE='hashicorp/terraform-mcp-server@sha256:11dd418bba6003dd5777e9d0979b68de59929a155b355f338f407947e00e9d80'
VERSION='1.4.1'
CONTAINER="${IACG_HERMES_CONTAINER:-iacgenius}"
DATA="${IACG_HERMES_DATA:-/data/hermes}"
DEST="$DATA/installs/terraform-mcp/$VERSION"
test "$(uname -m)" = x86_64 || { echo 'This reviewed installer supports Linux x86_64 only.' >&2; exit 1; }
test -d "$DATA/profiles/iacgenius" || { echo 'IaC Genius profile not found.' >&2; exit 1; }
docker inspect "$CONTAINER" >/dev/null
docker pull "$IMAGE"
EXTRACT=$(docker create "$IMAGE")
trap 'docker rm "$EXTRACT" >/dev/null' EXIT
mkdir -p "$DEST"
docker cp "$EXTRACT:/bin/terraform-mcp-server" "$DEST/terraform-mcp-server"
chmod 755 "$DEST/terraform-mcp-server"
sha256sum "$DEST/terraform-mcp-server"
# /opt/data is the standard container mount of DATA. No credentials are forwarded to this MCP.
docker exec -i --user 10000:10000 -e HERMES_HOME=/opt/data/profiles/iacgenius "$CONTAINER" python - <<'PY'
from hermes_cli.mcp_config import _get_mcp_servers, _save_mcp_server
names = ['search_provider_docs', 'get_provider_details', 'get_provider_capabilities',
         'get_latest_provider_version', 'search_modules', 'get_module_details', 'get_latest_module_version']
config = {'command': '/usr/bin/env',
          'args': ['-i', 'HOME=/nonexistent', 'PATH=/usr/bin:/bin',
                   '/opt/data/installs/terraform-mcp/1.4.1/terraform-mcp-server', 'stdio', '--tools='+','.join(names)],
          'tools': {'include': names}}
existing = _get_mcp_servers().get('terraform-registry')
if existing is not None:
    if any(existing.get(k) != config[k] for k in ('command', 'args', 'tools')):
        raise SystemExit('Existing terraform-registry differs. Preserved it; review the connection in Hermes.')
    print('Existing matching Terraform Registry connection preserved, including its enabled state.')
elif not _save_mcp_server('terraform-registry', config):
    raise SystemExit('Hermes rejected the connection. No successful configuration claimed.')
else:
    print('Terraform Registry connection added with seven public read tools.')
PY
echo 'Start a fresh chat and request a version-specific resource example to test terraform-registry.'