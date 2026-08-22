"""Entrypoint for the web-kernel and CLI tools (imperal validate/build).

Sets up sys.path, purges stale module cache, then imports ext/chat and all
handler modules so their decorators register on the same Extension
instance -- same pattern as CircleCI Connector's / Redox Connector's
main.py.
"""

import os
import sys

_EXT_DIR = os.path.dirname(os.path.abspath(__file__))
if _EXT_DIR not in sys.path:
    sys.path.insert(0, _EXT_DIR)

_LOCAL = (
    "app", "schemas", "docusign_client",
    "handlers_connection", "handlers_envelope", "handlers_template",
    "handlers_bulk_send", "handlers_powerform", "handlers_folder",
    "handlers_admin", "handlers_brand", "handlers_connect_webhook",
    "handlers_account", "handlers_bulk_audit",
    "panels", "panels_settings",
)
for _mod in _LOCAL:
    sys.modules.pop(_mod, None)

from app import ext, chat  # noqa: E402,F401
import handlers_connection  # noqa: E402,F401
import handlers_envelope  # noqa: E402,F401
import handlers_template  # noqa: E402,F401
import handlers_bulk_send  # noqa: E402,F401
import handlers_powerform  # noqa: E402,F401
import handlers_folder  # noqa: E402,F401
import handlers_admin  # noqa: E402,F401
import handlers_brand  # noqa: E402,F401
import handlers_connect_webhook  # noqa: E402,F401
import handlers_account  # noqa: E402,F401
import handlers_bulk_audit  # noqa: E402,F401
import panels  # noqa: E402,F401
import panels_settings  # noqa: E402,F401
