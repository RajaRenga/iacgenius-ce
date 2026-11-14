"""IaC Genius CE board dashboard plugin.

The tab backend lives in dashboard/plugin_api.py (mounted by the dashboard via
manifest.json "api"). This package marker lets the Hermes plugin loader import the
plugin; the board itself is served from the snapshot the desk writes.
"""