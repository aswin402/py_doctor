git clone https://github.com/yourname/py_doctor
cd py_doctor
./tool/activate.sh


Replace both files with these updated versions that include the symlink fix:

**`tool/activate.sh`:**
```bash
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

# symlink to /usr/local/bin so it works from any directory
PYDOC=$(find ~ -name "py_doctor" -type f 2>/dev/null | head -1)
if [ -n "$PYDOC" ]; then
    sudo ln -sf "$PYDOC" /usr/local/bin/py_doctor
    echo "✓ Symlink created: $PYDOC → /usr/local/bin/py_doctor"
else
    echo "Warning: binary not found, adding uv tools to PATH instead"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
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
```

**`tool/update.sh`:**
```bash
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
```

Make both executable:
```bash
chmod +x tool/activate.sh tool/update.sh
```

Now your full workflow is:

```bash
# someone new installs it:
git clone https://github.com/yourname/py_doctor
cd py_doctor
./tool/activate.sh
py_doctor . --verbose   # works from anywhere immediately

# you add a feature:
# 1. edit code
# 2. bump version in pyproject.toml
# 3. run:
./tool/update.sh
py_doctor . --verbose   # updated everywhere instantly
```