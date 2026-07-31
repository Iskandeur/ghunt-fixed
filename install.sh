#!/usr/bin/env bash
# ghunt-fixed installer.
#
# Goal: `ghunt` works after running this, with zero manual troubleshooting,
# regardless of whether pipx is preinstalled, whether the system Python is
# "externally managed" (PEP 668, the default on Ubuntu 23.04+/Debian 12+),
# or whether the user has sudo.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Iskandeur/ghunt-fixed/master/install.sh | bash
# or, after cloning the repo:
#   ./install.sh

set -euo pipefail

REPO_URL="https://github.com/Iskandeur/ghunt-fixed.git"
VENV_DIR="$HOME/.local/share/ghunt-fixed-venv"
BIN_DIR="$HOME/.local/bin"

log() { printf '[ghunt-fixed installer] %s\n' "$1"; }
die() { printf '[ghunt-fixed installer] ERROR: %s\n' "$1" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required but wasn't found. Install Python 3.10+ first."

PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
[ "$PY_OK" = "1" ] || die "Python 3.10+ is required. Found: $(python3 --version)."

install_via_existing_pipx() {
    command -v pipx >/dev/null 2>&1 || return 1
    log "pipx found, installing with it..."
    pipx install --force "git+${REPO_URL}"
    return 0
}

install_via_apt_pipx() {
    command -v apt-get >/dev/null 2>&1 || return 1

    local SUDO=""
    if [ "$(id -u)" != "0" ]; then
        command -v sudo >/dev/null 2>&1 || return 1
        SUDO="sudo"
    fi

    log "Installing pipx via apt (needs sudo)..."
    $SUDO apt-get update -qq && $SUDO apt-get install -y -qq pipx || return 1

    export PATH="$HOME/.local/bin:$PATH"
    pipx ensurepath >/dev/null 2>&1 || true
    log "Installing ghunt-fixed with pipx..."
    pipx install --force "git+${REPO_URL}"
    return 0
}

install_via_isolated_venv() {
    # Universal fallback: needs no sudo, no pipx, and can't hit PEP 668
    # (a venv is never "externally managed"). This is what pipx itself
    # would do under the hood, done by hand.
    log "Falling back to a dedicated virtual environment (no sudo/pipx needed)..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    log "Installing ghunt-fixed (this pulls in a few dependencies, may take a minute)..."
    "$VENV_DIR/bin/pip" install -q "git+${REPO_URL}"

    mkdir -p "$BIN_DIR"
    ln -sf "$VENV_DIR/bin/ghunt" "$BIN_DIR/ghunt"
    return 0
}

log "Installing ghunt-fixed from ${REPO_URL} ..."

if install_via_existing_pipx; then
    METHOD="pipx"
elif install_via_apt_pipx; then
    METHOD="pipx (via apt)"
else
    install_via_isolated_venv
    METHOD="venv"
fi

log "Installed successfully (method: ${METHOD})."

if ! command -v ghunt >/dev/null 2>&1; then
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            log "$BIN_DIR isn't on your PATH yet in this shell."
            log "Run:  export PATH=\"$BIN_DIR:\$PATH\""
            log "...or just open a new terminal (most shells pick up ~/.local/bin automatically)."
            ;;
    esac
fi

log "Run 'ghunt login' to authenticate, then e.g. 'ghunt email someone@example.com'."
