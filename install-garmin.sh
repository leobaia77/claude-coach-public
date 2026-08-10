#!/usr/bin/env bash
# Garmin Connect MCP — manual install for Cowork / Claude Code on macOS
# Run this from a Terminal on your Mac (not inside Cowork).
# Then restart the Claude desktop app for the new MCP to register.

set -euo pipefail

echo "=== Garmin Connect MCP installer ==="
echo

# 1. Ensure uv (Python package manager) is installed
if ! command -v uv >/dev/null 2>&1; then
  echo "[1/5] Installing 'uv'…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv installs to ~/.local/bin — make sure it's on PATH for this shell
  export PATH="$HOME/.local/bin:$PATH"
else
  echo "[1/5] uv already installed: $(uv --version)"
fi

# 2. Clone the leobaia77 fork (adds schedule/unschedule actions to manage-workouts)
PROJECT_DIR="$HOME/projects/garmin-connect-mcp"
if [ -d "$PROJECT_DIR/.git" ]; then
  echo "[2/5] Repo already cloned, pulling latest…"
  git -C "$PROJECT_DIR" pull --ff-only
else
  echo "[2/5] Cloning leobaia77/garmin-connect-mcp into $PROJECT_DIR…"
  mkdir -p "$HOME/projects"
  git clone https://github.com/leobaia77/garmin-connect-mcp.git "$PROJECT_DIR"
fi

# 3. Install dependencies
echo "[3/5] uv sync…"
uv sync --directory "$PROJECT_DIR"

# 4. Authenticate to Garmin Connect (prompts for email + password, may need MFA)
echo "[4/5] Authenticating to Garmin Connect (you'll be prompted for credentials)…"
uv run --directory "$PROJECT_DIR" garmin-connect-mcp-auth

# 5. Register the MCP with Claude Code (user scope, so all projects see it)
echo "[5/5] Registering Garmin MCP with Claude Code (user scope)…"
claude mcp add --scope user garmin -- uv run --directory "$PROJECT_DIR" garmin-connect-mcp

echo
echo "=== ✅ Done. ==="
echo "Now: quit and reopen the Claude desktop app so the new MCP loads."
echo "Then in this conversation, say: 'Garmin is installed — refresh zones and update the wiki.'"
