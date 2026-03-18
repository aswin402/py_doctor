#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "Updating py_doctor..."

uv tool install . --reinstall

# re-symlink because binary path may change after reinstall
PYDOC=$(find ~ -name "py_doctor" -type f 2>/dev/null | head -1)
if [ -n "$PYDOC" ]; then
    sudo ln -sf "$PYDOC" /usr/local/bin/py_doctor
    echo "✓ Symlink updated → $PYDOC"
fi

echo "✓ py_doctor updated successfully"
echo ""
py_doctor --help