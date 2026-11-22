"""
ghunt-fixed addition: obtain a fresh oauth_token without the GHunt Companion extension.

Google sets an `oauth_token` cookie (value starts with "oauth2_4/") on accounts.google.com
at the end of the EmbeddedSetup sign-in flow. That token is single-use and short-lived,
so it must be exchanged for a master token right away.

Two ways to get it:
- manual_flow(): opens the sign-in page in the default browser, the user copies the cookie.
- auto_flow():   launches Chrome/Edge/Chromium with a fresh, throwaway profile and the
                 DevTools protocol enabled, waits for the user to sign in, and reads the
                 cookie itself. No extra dependency: a minimal WebSocket client is below.
"""
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

LOGIN_URL = "https://accounts.google.com/EmbeddedSetup"
TOKEN_PREFIX = "oauth2_4/"
USED_TOKENS_FILE = Path.home() / ".malfrats" / "ghunt" / "used_tokens"


# ---------------------------------------------------------------- stale token guard

def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def is_token_already_used(token: str) -> bool:
    try:
        return _fingerprint(token) in USED_TOKENS_FILE.read_text(encoding="utf-8").split()
    except OSError:
        return False

def remember_used_token(token: str) -> None:
    """Store only a hash: the token itself is never written to disk."""
    try:
        USED_TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        if USED_TOKENS_FILE.is_file():
            lines = USED_TOKENS_FILE.read_text(encoding="utf-8").split()
        lines = (lines + [_fingerprint(token)])[-50:]
        USED_TOKENS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass

def check_token(token: str) -> Optional[str]:
    """Returns an error message if the token is obviously unusable, else None."""
    if not token.startswith(TOKEN_PREFIX):
        return f'This doesn\'t look like an oauth_token (it should start with "{TOKEN_PREFIX}").'
    if is_token_already_used(token):
        return ("This oauth_token was already used: Google only accepts it once.\n"
                "    Sign in again to get a fresh one (a private window helps), or delete the\n"
                "    \"oauth_token\" cookie of accounts.google.com, and retry.\n"
                "    If you use the GHunt Companion extension, it may be resending a cached token:\n"
                "    remove and reinstall it, or use `ghunt login` option [1] or [2] instead.")
    return None


# ---------------------------------------------------------------- manual flow

MANUAL_STEPS = f"""
[Browser login, manual]
 1. Open a PRIVATE / incognito window and go to:
      {LOGIN_URL}
 2. Sign in completely (2FA included). A blank or error page at the end is normal.
 3. Press F12 -> "Application" tab (Chrome/Edge) or "Storage" tab (Firefox)
    -> Cookies -> https://accounts.google.com
 4. Copy the value of the "oauth_token" cookie (starts with "{TOKEN_PREFIX}").
 5. Paste it below right away: it expires within minutes and works only once.
"""

def manual_flow() -> str:
    print(MANUAL_STEPS)
    try:
        webbrowser.open(LOGIN_URL)
    except Exception:
        pass
    while True:
        token = input("oauth_token => ").strip().strip('"\' ')
        error = check_token(token)
        if not error:
            return token
        print(f"[-] {error}\n")


# ---------------------------------------------------------------- automatic flow

def find_browser() -> Optional[str]:
    env = os.environ.get("GHUNT_BROWSER")
    if env:
        return env
    if sys.platform == "win32":
        candidates = []
        for base in filter(None, [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                                  os.environ.get("LOCALAPPDATA")]):
            candidates += [
                Path(base) / "Google/Chrome/Application/chrome.exe",
                Path(base) / "Microsoft/Edge/Application/msedge.exe",
                Path(base) / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(base) / "Chromium/Application/chrome.exe",
            ]
        for c in candidates:
            if c.is_file():
                return str(c)
        return None
    if sys.platform == "darwin":
        for app in ["Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium"]:
            p = Path(f"/Applications/{app}.app/Contents/MacOS/{app}")
            if p.is_file():
                return str(p)
        return None
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "microsoft-edge-stable", "brave-browser"]:
        path = shutil.which(name)
        if path:
            return path
    return None


class _MiniWebSocket:
    """Just enough of RFC 6455 to talk to the local Chrome DevTools endpoint."""

    def __init__(self, url: str):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("DevTools closed the connection during the handshake")
            resp += chunk
        if b" 101 " not in resp.split(b"\r\n", 1)[0]:
            raise ConnectionError("DevTools refused the WebSocket handshake")
        self.buf = resp.split(b"\r\n\r\n", 1)[1]

    def send(self, text: str) -> None:
        data = text.encode()
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header += bytes([0x80 | 126]) + n.to_bytes(2, "big")
        else:
            header += bytes([0x80 | 127]) + n.to_bytes(8, "big")
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("DevTools connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> str:
        message = b""
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n == 126:
                n = int.from_bytes(self._read(2), "big")
            elif n == 127:
                n = int.from_bytes(self._read(8), "big")
            if b1 & 0x80:
                mask = self._read(4)
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._read(n)))
            else:
                payload = self._read(n)
            opcode = b0 & 0x0F
            if opcode == 0x8:
                raise ConnectionError("DevTools connection closed")
            if opcode in (0x0, 0x1, 0x2):
                message += payload
                if b0 & 0x80:
                    return message.decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def _devtools_ws_url(port: int, deadline: float) -> str:
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.load(r)["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("The browser's DevTools endpoint never came up.")

def _get_oauth_cookie(ws: _MiniWebSocket, msg_id: int) -> Optional[str]:
    ws.send(json.dumps({"id": msg_id, "method": "Storage.getCookies"}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == msg_id:
            break
    for cookie in msg.get("result", {}).get("cookies", []):
        if cookie.get("name") == "oauth_token" and cookie.get("value", "").startswith(TOKEN_PREFIX):
            return cookie["value"]
    return None

def auto_flow(timeout: int = 600) -> str:
    """Launch a throwaway browser profile, let the user sign in, grab the oauth_token cookie."""
    browser = find_browser()
    if not browser:
        raise RuntimeError("No Chrome, Edge, Brave or Chromium found. Set GHUNT_BROWSER to the "
                           "browser executable, or use the manual browser login instead.")

    port = _free_port()
    profile = tempfile.mkdtemp(prefix="ghunt-login-")
    proc = subprocess.Popen(
        [browser, f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "--new-window", LOGIN_URL],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"[+] Opened {Path(browser).stem} with a fresh, temporary profile.")
    print("    Sign in to your Google account in that window (2FA included).")
    print("    GHunt will pick up the token by itself and close the window. Ctrl+C to abort.\n")

    ws = None
    try:
        deadline = time.time() + timeout
        ws = _MiniWebSocket(_devtools_ws_url(port, time.time() + 30))
        msg_id = 0
        while time.time() < deadline:
            msg_id += 1
            token = _get_oauth_cookie(ws, msg_id)
            if token:
                print("[+] Got a fresh oauth_token from the browser.")
                return token
            if proc.poll() is not None:
                raise RuntimeError("The browser window was closed before the sign-in finished.")
            time.sleep(1)
        raise TimeoutError("Timed out waiting for the Google sign-in.")
    finally:
        if ws:
            ws.close()
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(profile, ignore_errors=True)
