#!/usr/bin/env sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "Installing py_doctor..."

# install uv if not present
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found — installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# install py_doctor globally with uv tool
uv tool install .

# find binary from uv tool bin directory
PYDOC_DIR="$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")"
PYDOC="$PYDOC_DIR/py_doctor"
if [ -f "$PYDOC" ]; then
    if [ -w /usr/local/bin ]; then
        ln -sf "$PYDOC" /usr/local/bin/py_doctor
        echo "✓ Symlink created: $PYDOC → /usr/local/bin/py_doctor"
    elif command -v sudo >/dev/null 2>&1; then
        sudo ln -sf "$PYDOC" /usr/local/bin/py_doctor
        echo "✓ Symlink created: $PYDOC → /usr/local/bin/py_doctor"
    else
        echo "✓ Installed to $PYDOC (ensure $PYDOC_DIR is in your PATH)"
    fi
else
    echo "Warning: binary not found in $PYDOC_DIR, ensure uv tools directory is in PATH"
fi

echo ""
echo "✓ py_doctor installed successfully"
echo ""
echo "Usage:"
echo "  py_doctor .                 # scan current project"
echo "  py_doctor . --verbose       # with file:line details"
echo "  py_doctor . --score         # CI score only"
echo "  py_doctor /path/to/project  # scan specific project"
echo ""
echo "Test it now:"
echo "  py_doctor --help"