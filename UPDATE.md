# step 1 — make your code changes

# step 2 — bump version in pyproject.toml

# change version = "1.0.0" → "1.0.1"

# step 3 — reinstall

cd /home/aswin/programming/vscode/myProjects/py_doctor
uv tool install . --reinstall

# step 4 — re-symlink (binary path changes with new version)

PYDOC=$(find ~ -name "py_doctor" -type f 2>/dev/null | head -1)
sudo ln -sf "$PYDOC" /usr/local/bin/py_doctor

# step 5 — verify

py_doctor --help
py_doctor . --verbose

# make changes to any file

# bump version in pyproject.toml

./tool/update.sh # one command does everything
py_doctor /path/to/any/project --verbose
