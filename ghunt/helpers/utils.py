from pathlib import Path
from PIL import Image
import hashlib
from typing import *
from time import time
from datetime import datetime, timezone
from dateutil.parser import isoparse
from copy import deepcopy
import jsonpickle
import json
from packaging.version import parse as parse_version

import httpx
import imagehash
from io import BytesIO

from ghunt import globals as gb
from ghunt import version as current_version
from ghunt.lib.httpx import AsyncClient


def get_httpx_client() -> httpx.AsyncClient:
    """
        Returns a customized to better support the needs of GHunt CLI users.
    """
    return AsyncClient(http2=True, timeout=15)
    # return AsyncClient(http2=True, timeout=15, proxies="http://127.0.0.1:8282", verify=False)

def is_stdout_target(json_file: Path) -> bool:
    """Whether a --json argument means "write to stdout" rather than to a file."""
    return json_file is not None and str(json_file) == "-"

def wants_json_stdout(argv: List[str]) -> bool:
    """Lightweight pre-parse of raw argv for --json -/--json=-, used before
    argparse has run (banner/version-check print before any subcommand parsing)."""
    for i, arg in enumerate(argv):
        if arg == "--json" and i + 1 < len(argv) and argv[i + 1] == "-":
            return True
        if arg == "--json=-":
            return True
    return False

def redirect_console_output_to_stderr() -> None:
    """
        Called when --json - was requested: repoints gb.rc and the print()
        builtin at stderr, so stdout carries nothing but the final JSON
        payload written via write_json_output() — safe to pipe into jq,
        a script, or an LLM harness without any banner/progress noise mixed in.
    """
    import sys
    import builtins
    from rich.console import Console
    from ghunt.objects.utils import TMPrinter

    gb.rc = Console(highlight=False, file=sys.stderr)

    # TMPrinter (used for in-place progress lines like "Dumped N events...")
    # shares a single Console instance across every TMPrinter() call site via
    # a mutable default argument, independent of gb.rc — redirect it too.
    TMPrinter().rc.file = sys.stderr

    if not getattr(builtins.print, "_ghunt_stderr_wrapped", False):
        _orig_print = builtins.print
        def _stderr_print(*args, **kwargs):
            kwargs.setdefault("file", sys.stderr)
            _orig_print(*args, **kwargs)
        _stderr_print._ghunt_stderr_wrapped = True
        builtins.print = _stderr_print

def write_json_output(data: any, json_file: Path) -> None:
    """
        Writes `data` as JSON to json_file, using GHuntEncoder for GHunt objects.
        If json_file is "-" (ghunt-fixed addition), writes straight to the real
        stdout instead of a file, so it can be piped into other tools (jq, a
        script, an LLM harness, ...) without touching the filesystem.
    """
    from ghunt.objects.encoders import GHuntEncoder
    import sys

    payload = json.dumps(data, cls=GHuntEncoder, indent=4)

    if is_stdout_target(json_file):
        sys.stdout.write(payload + "\n")
        sys.stdout.flush()
    else:
        with open(json_file, "w", encoding="utf-8") as f:
            f.write(payload)
        gb.rc.print(f"\n[+] JSON output wrote to {json_file} !", style="italic")

def oprint(obj: any) -> str:
    serialized = jsonpickle.encode(obj)
    pretty_output = json.dumps(json.loads(serialized), indent=2)
    print(pretty_output)

def chunkify(lst, n):
    """
        Cut a given list to chunks of n items.
    """
    k, m = divmod(len(lst), n)
    for i in range(n):
        yield lst[i*k+min(i, m):(i+1)*k+min(i+1, m)]

def within_docker() -> bool:
    return Path('/.dockerenv').is_file()

def gen_sapisidhash(sapisid: str, origin: str, timestamp: str = str(int(time()))) -> str:
    return f"{timestamp}_{hashlib.sha1(' '.join([timestamp, sapisid, origin]).encode()).hexdigest()}"

def inject_osid(cookies: Dict[str, str], osids: Dict[str, str], service: str) -> Dict[str, str]:
    cookies_with_osid = deepcopy(cookies)
    cookies_with_osid["OSID"] = osids[service]
    return cookies_with_osid
    
def is_headers_syntax_good(headers: Dict[str, str]) -> bool:
    try:
        httpx.Headers(headers)
        return True
    except:
        return False

async def get_url_image_flathash(as_client: httpx.AsyncClient, image_url: str) -> str:
    req = await as_client.get(image_url)
    img = Image.open(BytesIO(req.content))
    flathash = imagehash.average_hash(img)
    return str(flathash)

async def is_default_profile_pic(as_client: httpx.AsyncClient, image_url: str) -> Tuple[bool, str]:
    """
        Returns a boolean which indicates if the image_url
        is a default profile picture, and the flathash of
        the image.
    """
    flathash = await get_url_image_flathash(as_client, image_url)
    if imagehash.hex_to_flathash(flathash, 8) - imagehash.hex_to_flathash("000018183c3c0000", 8) < 10 :
        return True, str(flathash)
    return False, str(flathash)

def get_class_name(obj) -> str:
        return str(obj).strip("<>").split(" ")[0]

def get_datetime_utc(date_str):
    """Converts ISO to datetime object in UTC"""
    date = isoparse(date_str)
    margin = date.utcoffset()
    return date.replace(tzinfo=timezone.utc) - margin

def ppnb(nb: float|int) -> float:
    """
        Pretty print float number
        Ex: 3.9 -> 3.9
            4.0 -> 4
            4.1 -> 4.1
    """
    try:
        return int(nb) if nb % int(nb) == 0.0 else nb
    except ZeroDivisionError:
        if nb == 0.0:
            return 0
        else:
            return nb

def parse_oauth_flow_response(body: str):
    """
        Correctly format the response sent by android.googleapis.com
        during the Android OAuth2 Login Flow.
    """
    return {sp[0]:'='.join(sp[1:]) for x in body.split("\n") if (sp := x.split("="))}

def humanize_list(array: List[any]):
    """
        Transforms a list to a human sentence.
        Ex : ["reader", "writer", "owner"] -> "reader, writer and owner".
    """
    if len(array) <= 1:
        return ''.join(array)

    final = ""
    for nb, item in enumerate(array):
        if nb == 0:
            final += f"{item}"
        elif nb+1 < len(array):
            final += f", {item}"
        else:
            final += f" and {item}"
    return final

def unicode_patch(txt: str):
    bad_chars = {
        "é": "e",
        "è": "e",
        "ç": "c",
        "à": "a"
    }
    return txt.replace(''.join([*bad_chars.keys()]), ''.join([*bad_chars.values()]))

def detect_install_method() -> tuple[str, str]:
    """
        Best-effort detection of how ghunt-fixed was installed, so update
        guidance (and `ghunt update`) can suggest, or run, the right command
        instead of always assuming pipx.
        Returns (method, path) where method is "pipx", "venv", or "unknown".
    """
    import sys
    prefix = sys.prefix
    if "pipx" in Path(prefix).parts:
        return "pipx", prefix
    if Path(prefix).name == "ghunt-fixed-venv":
        return "venv", prefix
    return "unknown", prefix

def upgrade_command_hint() -> str:
    """A copy-pasteable command to upgrade ghunt-fixed, matching how it was installed."""
    method, path = detect_install_method()
    if method == "pipx":
        return "pipx upgrade ghunt-fixed"
    if method == "venv":
        return f"{path}/bin/pip install --upgrade git+https://github.com/Iskandeur/ghunt-fixed.git"
    return "ghunt update  (or: pip install --upgrade git+https://github.com/Iskandeur/ghunt-fixed.git)"

def show_version():
    new_version, new_metadata = check_new_version()
    print()
    gb.rc.print(f"> GHunt-Fixed {current_version.metadata.get('version', '')} ({current_version.metadata.get('name', '')}) <".center(53), style="bold")
    print()
    if new_version:
        gb.rc.print(f"🥳 New version {new_metadata.get('version', '')} ({new_metadata.get('name', '')}) is available !", style="bold red")
        gb.rc.print(f"🤗 Run '{upgrade_command_hint()}' to update.", style="bold light_pink3")
    else:
        gb.rc.print("🎉 You are up to date !", style="light_pink3")


def check_new_version() -> tuple[bool, dict[str, str]]:
    """
        Checks if there is a new version of ghunt-fixed available.
    """
    req = httpx.get("https://raw.githubusercontent.com/Iskandeur/ghunt-fixed/master/ghunt/version.py")
    if req.status_code != 200:
        return False, {}
    
    raw = req.text.strip().removeprefix("metadata = ")
    data = json.loads(raw)
    new_version = data.get("version", "")
    new_name = data.get("name", "")

    if parse_version(new_version) > parse_version(current_version.metadata.get("version", "")):
        return True, {"version": new_version, "name": new_name}
    return False, {}