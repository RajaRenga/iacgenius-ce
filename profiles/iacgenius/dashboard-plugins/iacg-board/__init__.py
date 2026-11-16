"""IaC Genius CE board dashboard plugin.

The tab backend lives in dashboard/plugin_api.py (mounted by the dashboard via
manifest.json "api"). This package marker lets the Hermes plugin loader import the
plugin; the board itself is served from the snapshot the desk writes.
"""


def register(ctx):
    """Dashboard-only plugin: the tab is mounted via dashboard/manifest.json (entry + css + api),
    not through agent tools/hooks. register() declares no agent capabilities, matching the catalog
    entry's empty provides_tools / provides_hooks / provides_middleware. The board is read-only and
    served from the snapshot the desk writes."""
    return None