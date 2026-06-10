#!/bin/bash
#
# Deprecated: use ./install.sh at the project root.
# Kept as a thin wrapper for backwards compatibility.
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$(dirname "$SCRIPT_DIR")/install.sh" "$@"
