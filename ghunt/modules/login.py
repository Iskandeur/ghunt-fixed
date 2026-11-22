import os
import sys
from typing import *

import httpx
from pathlib import Path

from ghunt import globals as gb
from ghunt.helpers.utils import *
from ghunt.helpers import auth
from ghunt.objects.base import GHuntCreds
from ghunt.errors import GHuntInvalidSession


async def check_and_login(as_client: httpx.AsyncClient, clean: bool=False, non_interactive: bool=False,
                           check: bool=False, oauth_token: str=None, master_token: str=None,
                           json_file: Path=None, browser: bool=False) -> None:
    """Check the users credentials validity, and generate new ones."""

    ghunt_creds = GHuntCreds()

    if clean:
        creds_path = Path(ghunt_creds.creds_path)
        if creds_path.is_file():
            creds_path.unlink()
            print(f"[+] Credentials file at {creds_path} deleted !")
        else:
            print(f"Credentials file at {creds_path} doesn't exists, no need to delete.")
        exit(os.EX_OK)

    if not as_client:
        as_client = get_httpx_client()

    # ghunt-fixed addition: never block on input() when automated. --check and
    # explicit credentials always skip prompts; --non-interactive and a non-tty
    # stdin (e.g. run from a script/cron/LLM harness) do too.
    oauth_token = oauth_token or os.environ.get("GHUNT_OAUTH_TOKEN")
    master_token = master_token or os.environ.get("GHUNT_MASTER_TOKEN")
    non_interactive = non_interactive or check or bool(oauth_token) or bool(master_token) or not sys.stdin.isatty()

    is_session_valid = True
    try:
        ghunt_creds = await auth.load_and_auth(as_client, help=False)
    except GHuntInvalidSession as e:
        print(f"[-] {e}\n")
        is_session_valid = False

    if check:
        status = {
            "session_found": is_session_valid,
            "master_token_valid": None,
            "cookies_valid": None,
            "osids_valid": None,
            "session_valid": False,
        }
        if is_session_valid:
            status["master_token_valid"] = await auth.check_master_token(as_client, ghunt_creds.android.master_token)
            status["cookies_valid"] = await auth.check_cookies(as_client, ghunt_creds.cookies)
            status["osids_valid"] = await auth.check_osids(as_client, ghunt_creds.cookies, ghunt_creds.osids)
            status["session_valid"] = all([status["master_token_valid"], status["cookies_valid"], status["osids_valid"]])
        await as_client.aclose()

        if json_file:
            write_json_output(status, json_file)
        else:
            gb.rc.print(status)
        exit(os.EX_OK if status["session_valid"] else 1)

    if browser and not (oauth_token or master_token):
        from ghunt.helpers import browser_login
        oauth_token = browser_login.auto_flow()

    if oauth_token or master_token:
        # Explicit credentials (flag or env var) always take priority: skip
        # straight to regenerating the session below, no prompt needed.
        pass
    elif not is_session_valid:
        if non_interactive:
            await as_client.aclose()
            exit("[-] No valid stored session, and no --oauth-token/--master-token (or GHUNT_OAUTH_TOKEN/GHUNT_MASTER_TOKEN) supplied. Can't authenticate in non-interactive mode.")
        oauth_token, master_token = auth.auth_dialog()
    else:
        # in case user wants to enter new creds (example: for new account)
        is_master_token_valid = await auth.check_master_token(as_client, ghunt_creds.android.master_token)
        if is_master_token_valid:
            print("[+] The master token seems valid !")
        else:
            print("[-] Seems like the master token is invalid.")

        cookies_valid = await auth.check_cookies(as_client, ghunt_creds.cookies)
        if cookies_valid:
            print("[+] The cookies seem valid !")
        else:
            print("[-] Seems like the cookies are invalid.")

        osids_valid = await auth.check_osids(as_client, ghunt_creds.cookies, ghunt_creds.osids)
        if osids_valid:
            print("[+] OSIDs seem valid !")
        else:
            print("[-] Seems like OSIDs are invalid.")

        if non_interactive:
            gb.rc.print("\n[+] Non-interactive mode : keeping the existing stored session.", style="italic")
            await as_client.aclose()
            exit(os.EX_OK)

        new_gen_inp = input("\nDo you want to create a new session ? (Y/n) ").lower()
        if new_gen_inp == "y":
            oauth_token, master_token = auth.auth_dialog()
        else:
            exit(os.EX_OK)

    ghunt_creds.android.authorization_tokens = {} # Reset the authorization tokens

    if oauth_token:
        from ghunt.helpers import browser_login
        print(f"\n[+] Got OAuth2 token => {oauth_token[:16]}... (hidden)")
        try:
            master_token, services, owner_email, owner_name = await auth.android_master_auth(as_client, oauth_token)
        finally:
            # Single-use token: remember it (hashed) so a stale resend gets a clear error next time.
            browser_login.remember_used_token(oauth_token)

        print("\n[Connected account]")
        print(f"Name : {owner_name}")
        print(f"Email : {owner_email}")
        gb.rc.print("\n🔑 [underline]A master token has been generated for your account and saved in the credentials file[/underline], please keep it safe as if it were your password, because it gives access to a lot of Google services, and with that, your personal information.", style="bold")
        print(f"Master token services access : {', '.join(services)}")

    # Feed the GHuntCreds object
    ghunt_creds.android.master_token = master_token

    ghunt_creds.cookies = {"a": "a"} # Dummy ata
    ghunt_creds.osids = {"a": "a"} # Dummy data

    print("Generating cookies and osids...")
    await auth.gen_cookies_and_osids(as_client, ghunt_creds)
    print("[+] Cookies and osids generated !")

    ghunt_creds.save_creds()

    await as_client.aclose()
