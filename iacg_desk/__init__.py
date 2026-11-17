"""IaC Genius CE desk: deterministic mission state, evidence, gates and delivery."""
import os

__version__ = "0.1.0"

# Minimal environment for the validation toolchain (terraform / tflint / checkov). Never forward the
# desk's full environment: it may hold IACG_GITHUB_TOKEN or model-provider keys, and those tools — or
# any provider/module they load — must never see them. Allowlist only what the tools need to run and
# reach the public registry. (Hermes catalog admission rule 11: credentials stay scoped.)
_TOOL_ENV_KEEP = (
    "PATH", "HOME", "LANG", "LC_ALL", "USER", "LOGNAME", "SHELL", "TERM",
    "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "TF_PLUGIN_CACHE_DIR",
)


def tool_env(**extra):
    """A secret-free environment for validation subprocesses (allowlist, not os.environ)."""
    env = {k: os.environ[k] for k in _TOOL_ENV_KEEP if k in os.environ}
    env.setdefault("TF_IN_AUTOMATION", "1")
    env.setdefault("CHECKPOINT_DISABLE", "1")
    env.update(extra)
    return env