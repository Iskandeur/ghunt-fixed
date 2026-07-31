import subprocess
from pathlib import Path

from ghunt import globals as gb
from ghunt.helpers.utils import check_new_version, detect_install_method, write_json_output


def run(check_only: bool=False, json_file: Path=None) -> None:
    """
        Checks for (and, unless check_only, applies) an update to the latest
        commit of ghunt-fixed, using whichever install method (pipx / venv)
        was detected - so users don't have to remember which command matches
        how they installed it.
    """
    new_version_available, new_metadata = check_new_version()
    method, path = detect_install_method()

    if check_only:
        status = {
            "update_available": new_version_available,
            "latest_version": new_metadata.get("version"),
            "install_method": method,
        }
        if json_file:
            write_json_output(status, json_file)
        else:
            gb.rc.print(status)
        exit(0)

    if not new_version_available:
        gb.rc.print("🎉 Already up to date !", style="light_pink3")
        return

    gb.rc.print(f"[+] New version available : {new_metadata.get('version')} ({new_metadata.get('name')})", style="bold")

    if method == "pipx":
        cmd = ["pipx", "upgrade", "ghunt-fixed"]
    elif method == "venv":
        cmd = [str(Path(path) / "bin" / "pip"), "install", "--upgrade", "git+https://github.com/Iskandeur/ghunt-fixed.git"]
    else:
        gb.rc.print(
            "[!] Couldn't tell how ghunt-fixed was installed here, so it can't self-upgrade. Try one of :\n"
            "  pipx upgrade ghunt-fixed\n"
            "  pip install --upgrade git+https://github.com/Iskandeur/ghunt-fixed.git\n"
            "  (or, if running from a git clone : git pull)",
            style="yellow"
        )
        exit(1)

    gb.rc.print(f"[+] Running : {' '.join(cmd)}", style="italic")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        gb.rc.print("[+] Updated ! Re-run your command to use the new version.", style="bold sea_green3")
    exit(result.returncode)
