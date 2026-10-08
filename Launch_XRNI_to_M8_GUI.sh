#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed."
  echo "Install Python 3 using your Linux distribution's package manager."
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  echo "ERROR: Python Tkinter is not available."
  echo "Install it with your package manager, for example:"
  echo "  Debian/Ubuntu: sudo apt install python3-tk"
  echo "  Fedora:        sudo dnf install python3-tkinter"
  echo "  Arch:          sudo pacman -S tk"
  exit 1
fi

missing="$(python3 - <<'PY'
mods = [('numpy','numpy'), ('soundfile','soundfile')]
missing=[]
for module, package in mods:
    try:
        __import__(module)
    except ImportError:
        missing.append(package)
print(' '.join(missing))
PY
)"

if [ -n "$missing" ]; then
  echo "Installing required Python package(s): $missing"
  if ! python3 -m pip install --user $missing; then
    echo "ERROR: Could not install required packages automatically."
    echo "Try: python3 -m pip install --user numpy soundfile"
    echo "You may also need libsndfile from your Linux package manager."
    exit 1
  fi
fi

exec python3 "$SCRIPT_DIR/xrni_to_m8_gui.py"
