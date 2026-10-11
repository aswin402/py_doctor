#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "Updating py_doctor..."

uv tool install . --reinstall

# re-symlink because binary path may change after reinstall
PYDOC_DIR="$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")"
PYDOC="$PYDOC_DIR/py_doctor"
if [ -f "$PYDOC" ]; then
    if [ -w /usr/local/bin ]; then
        ln -sf "$PYDOC" /usr/local/bin/py_doctor
        echo "✓ Symlink updated → $PYDOC"
    elif command -v sudo >/dev/null 2>&1; then
        sudo ln -sf "$PYDOC" /usr/local/bin/py_doctor
        echo "✓ Symlink updated → $PYDOC"
    fi
fi

echo "✓ py_doctor updated successfully"
echo ""
py_doctor --help