![](assets/long_banner.png)

<br>

> ## 🔧 About this fork
>
> This is `ghunt-fixed`, a fork of [mxrch/GHunt](https://github.com/mxrch/GHunt) started on 2026-07-31
> because the official PyPI release (2.3.4) crashes with `KeyError: 'container'` on `ghunt email`
> for many accounts (Google's People API now sometimes omits `metadata.container`), and the upstream
> fix for it was stuck across several unmerged PRs. Everything below is a complete, transparent list
> of what differs from upstream GHunt — nothing is changed silently.
>
> **Bug fixes:**
> - Every `metadata.container` lookup in the People parser is guarded (email, name, profile info,
>   photos, source IDs, cover photo, in-app reachability) instead of crashing on the first missing
>   one — upstream only patched `coverPhoto`. Also submitted upstream as [PR #603](https://github.com/mxrch/GHunt/pull/603).
> - Fixed a real, separate bug where profile photos were keyed by the wrong container (whichever
>   profile-info container the outer loop happened to be on), silently mis-attributing/dropping photos.
> - `ghunt email` no longer hard-exits on Workspace/G Suite accounts that have no `PROFILE`
>   container — it now uses whatever container is actually available (e.g. `DOMAIN_PROFILE`).
> - The People parser now isolates each field's parsing: if Google changes the response shape
>   again in some new way, that one field logs a warning and gets skipped instead of crashing
>   the whole lookup.
>
> **New features:**
> - **Batch lookups**: `ghunt email -f addresses.txt` runs a list of addresses instead of one at a
>   time, skipping failures instead of aborting the whole batch.
> - **Machine-readable stdout**: pass `-` to `--json` on any module (`--json -`) to write pure JSON
>   to stdout instead of a file — every other line of output (banner, progress, prompts) moves to
>   stderr, so the output is safe to pipe straight into `jq`, a script, or an LLM/agent harness.
> - **Non-interactive login**: `ghunt login` no longer blocks on a prompt (and no longer crashes
>   with `EOFError`) when run from a script, cron job, or agent with no TTY attached. Add
>   `--check` to get a JSON-able auth status with zero prompts, or `--oauth-token`/`--master-token`
>   (or `GHUNT_OAUTH_TOKEN`/`GHUNT_MASTER_TOKEN` env vars) to script authentication end-to-end.
> - **Retries transient network errors**: connection drops/timeouts and 429/502/503/504 responses
>   are retried with exponential backoff instead of crashing the lookup immediately (upstream
>   issues [#469](https://github.com/mxrch/GHunt/issues/469), [#464](https://github.com/mxrch/GHunt/issues/464)).
> - **`ghunt update`**: checks for and applies updates using whichever install method is detected
>   (pipx or the manual venv), instead of a static "run `pipx upgrade`" message that's wrong for
>   half of install methods.
> - **One-command install** ([`install.sh`](install.sh)) that works out of the box even where a
>   plain `pip install pipx` fails with `externally-managed-environment` (PEP 668, the default on
>   current Ubuntu/Debian) — see the Installation section below.
>
> Still licensed under AGPLv3, same as upstream — see [LICENSE.md](LICENSE.md). This fork stays
> open under the same license; see [github.com/Iskandeur/ghunt-fixed](https://github.com/Iskandeur/ghunt-fixed)
> for the source, and `git fetch upstream` (remote already points at `mxrch/GHunt`) to pull in
> anything new upstream ships later.

<br>

#### 🌐 GHunt Online version : https://osint.industries
#### 🐍 Now Python 3.13 compatible !

<br>

![Python minimum version](https://img.shields.io/badge/Python-3.10%2B-brightgreen)

# 😊 Description

GHunt (v2) is an offensive Google framework, designed to evolve efficiently.\
It's currently focused on OSINT, but any use related with Google is possible.

Features :
- CLI usage and modules
- Python library usage
- Fully async
- JSON export
- Browser extension to ease login

# ✔️ Requirements
- Python >= 3.10

# ⚙️ Installation

Installs from this fork (`ghunt-fixed`), not the official PyPI `ghunt` package — the PyPI release
is the one that crashes on `ghunt email` for many accounts.

## One-liner (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/Iskandeur/ghunt-fixed/master/install.sh | bash
```

This runs [`install.sh`](install.sh) — worth a skim before piping it into `bash`, as with any
install script off the internet. It exists specifically because a plain `pip3 install pipx` fails
out of the box on current Ubuntu/Debian (`externally-managed-environment`, PEP 668) unless you
already know the right workaround. The script picks, in order, whichever of these actually works
on your machine, with **no manual troubleshooting**:

1. Uses `pipx` if it's already installed.
2. Otherwise installs `pipx` via `apt` (asks for `sudo` once) and uses that.
3. Otherwise falls back to a dedicated virtual environment at `~/.local/share/ghunt-fixed-venv`,
   symlinked to `~/.local/bin/ghunt` — no `sudo`, no `pipx`, and immune to PEP 668, since a venv is
   never "externally managed". This is exactly what `pipx` does under the hood, done by hand.

Open a new terminal afterwards (or `source ~/.bashrc` / `source ~/.zshrc`) if `ghunt` isn't found
immediately — the script tells you explicitly if that's needed.

Re-run the same command any time to update to the latest commit.

## Manual installation

If you'd rather not pipe a script into `bash`, do what it does yourself:

**On Debian/Ubuntu**, `apt`'s `pipx` avoids the PEP 668 error entirely:
```bash
sudo apt update && sudo apt install -y pipx
pipx ensurepath
```
Open a new terminal, then:
```bash
pipx install git+https://github.com/Iskandeur/ghunt-fixed.git
```
To update later: `pipx upgrade ghunt-fixed`

**Anywhere else** (macOS, no `sudo`, no `apt`, ...), a dedicated venv always works and needs
nothing preinstalled beyond Python itself:
```bash
python3 -m venv ~/.local/share/ghunt-fixed-venv
~/.local/share/ghunt-fixed-venv/bin/pip install --upgrade pip
~/.local/share/ghunt-fixed-venv/bin/pip install git+https://github.com/Iskandeur/ghunt-fixed.git
mkdir -p ~/.local/bin
ln -sf ~/.local/share/ghunt-fixed-venv/bin/ghunt ~/.local/bin/ghunt
```
`~/.local/bin` is already on `PATH` by default on most Linux distros and macOS; open a new terminal
if `ghunt` isn't found right away. To update later, re-run the `pip install` line above.

# 💃 Usage

## Login

First, launch the listener by doing `ghunt login` and choose between 1 of the 2 first methods :
```bash
ghunt login

[1] (Companion) Put GHunt on listening mode (currently not compatible with docker)
[2] (Companion) Paste base64-encoded cookies
[3] Enter manually all cookies

Choice =>
```

Then, use GHunt Companion to complete the login.

The extension is available on the following stores :\
\
[![Firefox](https://files.catbox.moe/5g2ld5.png)](https://addons.mozilla.org/en-US/firefox/addon/ghunt-companion/)&nbsp;&nbsp;&nbsp;[![Chrome](https://developer.chrome.com/static/docs/webstore/branding/image/206x58-chrome-web-bcb82d15b2486.png)](https://chrome.google.com/webstore/detail/ghunt-companion/dpdcofblfbmmnikcbmmiakkclocadjab)

## Modules

Then, profit :
```bash
Usage: ghunt [-h] {login,email,gaia,drive,geolocate,spiderdal,update} ...

Positional Arguments:
  {login,email,gaia,drive,geolocate,spiderdal,update}
    login               Authenticate GHunt to Google.
    email               Get information on an email address.
    gaia                Get information on a Gaia ID.
    drive               Get information on a Drive file or folder.
    geolocate           Geolocate a BSSID.
    spiderdal           Find assets using Digital Assets Links.
    update              Check for and apply ghunt-fixed updates.

Options:
  -h, --help            show this help message and exit
```

🔁 `ghunt-fixed` addition — `ghunt update` checks for and applies updates using whichever install
method it detects (pipx or the manual venv), so you don't need to remember which upgrade command
matches how you installed it:
```bash
ghunt update            # applies the update if one is available
ghunt update --check    # only reports whether one is available, doesn't apply it
```

📄 You can also use --json with email, gaia, drive and geolocate modules to export in JSON ! Example :

```bash
ghunt email <email_address> --json user_data.json
```

🔁 `ghunt-fixed` addition — batch lookup a list of addresses instead of one at a time:

```bash
ghunt email -f addresses.txt
ghunt email -f addresses.txt --json results_dir/   # one JSON file per address
```
`addresses.txt` is one email address per line; lines starting with `#` are ignored.

## 🤖 Automation / scripts / LLM usage (`ghunt-fixed` addition)

Everything below exists so `ghunt-fixed` can be driven by a script, a cron job, or an LLM agent
without ever hanging on a prompt or mixing human-readable text into machine-readable output.

**Check auth status without prompting anything:**
```bash
ghunt login --check --json -
```
Exits `0` with `"session_valid": true` if the stored session is good, `1` otherwise — never
prompts, never touches the credentials file. Drop `--json -` for a human-readable version instead.

**Authenticate without any interactive prompt**, using a token you already extracted (e.g. via
[GHunt Companion](https://github.com/mxrch/ghunt_companion)):
```bash
ghunt login --non-interactive --oauth-token "oauth2_4/xxxxxxxx"
# or, equivalently:
export GHUNT_OAUTH_TOKEN="oauth2_4/xxxxxxxx"
ghunt login --non-interactive
```
`ghunt login` run bare (no flags) also no longer crashes when there's no TTY attached (e.g. run from
a script) — it detects that automatically and just keeps the existing stored session instead of
blocking on a prompt.

**Get pure JSON on stdout** — pass `-` instead of a filename to `--json` on any module. Every bit of
human-readable output (banner, version check, progress, prompts) is routed to stderr instead, so
stdout is safe to pipe straight into `jq`, a script, or an LLM/agent harness:
```bash
ghunt email user@example.com --json - 2>/dev/null | jq .
```
This works the same way for `gaia`, `drive`, `geolocate`, `spiderdal`, and batch `email -f`
(one JSON document per address, printed back-to-back on stdout).

**A minimal end-to-end script an LLM/agent could run:**
```bash
if ! ghunt login --check --json - >/dev/null 2>&1; then
  echo "Not authenticated, run 'ghunt login' interactively first." >&2
  exit 1
fi
ghunt email user@example.com --json - 2>/dev/null
```

**Have fun 🥰💞**

# 🧑‍💻 Developers

📕 I started writing some docs [here](https://github.com/mxrch/GHunt/wiki) and examples [here](https://github.com/mxrch/GHunt/tree/master/examples), feel free to contribute !

To use GHunt as a lib, you can't use pipx because it uses a venv.\
So you should install it with pip instead, straight from this fork :
```bash
pip install git+https://github.com/Iskandeur/ghunt-fixed.git
```

And now, you should be able to `import ghunt` in your projects !\
You can right now play with the [examples](https://github.com/mxrch/GHunt/tree/master/examples).

# 📮 Details

## Obvious disclaimer

This tool is for educational purposes only, I am not responsible for its use.

## Less obvious disclaimer

This project is under [AGPL Licence](https://choosealicense.com/licenses/agpl-3.0/), and you have to respect it.\
**Use it only in personal, criminal investigations, pentesting, or open-source projects.**

## Thanks

- [novitae](https://github.com/novitae) for being my Python colleague
- All the people on [Malfrats Industries](https://discord.gg/sg2YcrC6x9) and elsewhere for the beta test !
- The HideAndSec team 💗 (blog : https://hideandsec.sh)
- [Med Amine Jouini](https://dribbble.com/jouiniamine) for his beautiful rework of the Google logo, which I was inspired by *a lot*.

## Sponsors

Thanks to these awesome people for supporting me !

<!-- sponsors --><a href="https://github.com/BlWasp"><img src="https://github.com/BlWasp.png" width="50px" alt="BlWasp" /></a>&nbsp;&nbsp;<a href="https://github.com/gingeleski"><img src="https://github.com/gingeleski.png" width="50px" alt="gingeleski" /></a>&nbsp;&nbsp;<!-- sponsors -->

\
You like my work ?\
[Sponsor me](https://github.com/sponsors/mxrch) on GitHub ! 🤗
