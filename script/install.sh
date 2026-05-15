#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/bin"
BINARY="$INSTALL_DIR/badger-push"

mkdir -p "$INSTALL_DIR"
cd "$SCRIPT_DIR"
go build -o "$BINARY" badger-push.go
echo "Installed $BINARY"

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$INSTALL_DIR"; then
  echo "Note: $INSTALL_DIR is not on your PATH."
  echo "Add this to your shell profile:  export PATH=\"\$HOME/bin:\$PATH\""
fi
