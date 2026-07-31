import os
import re

from ghunt import globals as gb
from ghunt.helpers.utils import get_httpx_client
from ghunt.objects.base import GHuntCreds
from ghunt.apis.peoplepa import PeoplePaHttp
from ghunt.apis.vision import VisionHttp
from ghunt.helpers import gmaps, playgames, auth, calendar as gcalendar, ia
from ghunt.helpers.knowledge import get_user_type_definition

import httpx

from typing import *
from pathlib import Path


async def hunt_many(addresses_file: Path, json_dir: Path=None):
    """
        Runs hunt() over every email address listed in addresses_file (one per line,
        '#'-prefixed lines ignored), continuing past individual failures instead of
        aborting the whole batch.
    """
    if not addresses_file.is_file():
        exit(f"[-] File not found: {addresses_file}")

    addresses = [
        line.strip()
        for line in addresses_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not addresses:
        exit(f"[-] No email addresses found in {addresses_file}")

    if json_dir:
        json_dir.mkdir(parents=True, exist_ok=True)

    gb.rc.print(f"[+] Loaded {len(addresses)} email address(es) from {addresses_file}", style="bold")

    failures = []
    for index, address in enumerate(addresses, start=1):
        gb.rc.print(f"\n{'=' * 60}\n[{index}/{len(addresses)}] {address}\n{'=' * 60}\n", style="bold plum2")

        json_file = None
        if json_dir:
            safe_name = re.sub(r"[^\w.@+-]", "_", address)
            json_file = json_dir / f"{safe_name}.json"

        try:
            await hunt(None, address, json_file)
        except SystemExit:
            # hunt() calls exit() when the target isn't found / has no usable
            # public data — treat that as a per-address skip, not a batch abort.
            failures.append(address)
        except Exception as e:
            gb.rc.print(f"[-] Unexpected error while processing {address}: {e}", style="bold red")
            failures.append(address)

    gb.rc.print(f"\n[+] Batch complete : {len(addresses) - len(failures)}/{len(addresses)} succeeded.", style="bold")
    if failures:
        gb.rc.print(f"[-] No usable data for : {', '.join(failures)}", style="italic")


async def hunt(as_client: httpx.AsyncClient, email_address: str, json_file: Path=None):
    if not as_client:
        as_client = get_httpx_client()
 
    ghunt_creds = await auth.load_and_auth(as_client)

    #gb.rc.print("[+] Target found !", style="sea_green3")

    people_pa = PeoplePaHttp(ghunt_creds)
    # vision_api = VisionHttp(ghunt_creds)
    is_found, target = await people_pa.people_lookup(as_client, email_address, params_template="max_details")
    if not is_found:
        print("[-] The target wasn't found.")
        await as_client.aclose()
        exit()

    if json_file:
        json_results = {}

    containers = target.sourceIds

    if len(containers) > 1 or not "PROFILE" in containers:
        print("[!] You have this person in these containers :")
        for container in containers:
            print(f"- {container.title()}")

    if not containers:
        print("[-] Given information does not match a public Google Account.")
        await as_client.aclose()
        exit()

    if "PROFILE" in containers:
        container = "PROFILE"
    else:
        # No public consumer PROFILE container (typical for Workspace/G Suite
        # accounts), but other containers (e.g. DOMAIN_PROFILE) still carry
        # data GHunt already fetched. Use the first one instead of dropping
        # the lookup entirely.
        container = next(iter(containers))
        print(f"[!] No 'PROFILE' container found, using '{container.title()}' instead (likely a Workspace/G Suite account, some fields may be limited).\n")
    
    gb.rc.print("🙋 Google Account data\n", style="plum2")

    # if container in target.names:
        # print(f"Name : {target.names[container].fullname}\n")

    if container in target.profilePhotos:
        if target.profilePhotos[container].isDefault:
            print("[-] Default profile picture")
        else:
            print("[+] Custom profile picture !")
            print(f"=> {target.profilePhotos[container].url}")
            
            # await ia.detect_face(vision_api, as_client, target.profilePhotos[container].url)
            print()

    if container in target.coverPhotos:
        if target.coverPhotos[container].isDefault:
            print("[-] Default cover picture\n")
        else:
            print("[+] Custom cover picture !")
            print(f"=> {target.coverPhotos[container].url}")

            # await ia.detect_face(vision_api, as_client, target.coverPhotos[container].url)
            print()

    if target.sourceIds[container].lastUpdated:
        print(f"Last profile edit : {target.sourceIds[container].lastUpdated.strftime('%Y/%m/%d %H:%M:%S (UTC)')}\n")
    else:
        gb.rc.print(f"Last profile edit : [italic]Not found.[/italic]\n")
    
    if container in target.emails:
        print(f"Email : {target.emails[container].value}")
    else:
        print(f"Email : {email_address}\n")

    print(f"Gaia ID : {target.personId}")

    if container in target.profileInfos:
        print("\nUser types :")
        for user_type in target.profileInfos[container].userTypes:
            definition = get_user_type_definition(user_type)
            gb.rc.print(f"- {user_type} [italic]({definition})[/italic]")

    gb.rc.print(f"\n📞 Google Chat Extended Data\n", style="light_salmon3")

    #print(f"Presence : {target.extendedData.dynamiteData.presence}")
    print(f"Entity Type : {target.extendedData.dynamiteData.entityType}")
    #print(f"DND State : {target.extendedData.dynamiteData.dndState}")
    gb.rc.print(f"Customer ID : {x if (x := target.extendedData.dynamiteData.customerId) else '[italic]Not found.[/italic]'}")

    gb.rc.print(f"\n🌐 Google Plus Extended Data\n", style="cyan")

    print(f"Entreprise User : {target.extendedData.gplusData.isEntrepriseUser}")
    #print(f"Content Restriction : {target.extendedData.gplusData.contentRestriction}")
    
    if container in target.inAppReachability:
        print("\n[+] Activated Google services :")
        for app in target.inAppReachability[container].apps:
            print(f"- {app}")

    gb.rc.print("\n🎮 Play Games data", style="deep_pink2")

    player_results = await playgames.search_player(ghunt_creds, as_client, email_address)
    if player_results:
        player_candidate = player_results[0]
        print("\n[+] Found player profile !")
        print(f"\nUsername : {player_candidate.name}")
        print(f"Player ID : {player_candidate.id}")
        print(f"Avatar : {player_candidate.avatar_url}")
        _, player = await playgames.get_player(ghunt_creds, as_client, player_candidate.id)
        playgames.output(player)
    else:
        print("\n[-] No player profile found.")

    gb.rc.print("\n🗺️ Maps data", style="green4")

    err, stats = await gmaps.get_reviews(as_client, target.personId)
    gmaps.output(err, stats, target.personId)

    gb.rc.print("\n🗓️ Calendar data\n", style="slate_blue3")

    cal_found, calendar, calendar_events = await gcalendar.fetch_all(ghunt_creds, as_client, email_address)

    if cal_found:
        print("[+] Public Google Calendar found !\n")
        if calendar_events.items:
            if container in target.names:
                gcalendar.out(calendar, calendar_events, email_address, target.names[container].fullname)
            else:
                gcalendar.out(calendar, calendar_events, email_address)
        else:
            print("=> No recent events found.")
    else:
        print("[-] No public Google Calendar.")

    if json_file:
        # Play Games / Maps / Calendar data is keyed by email address and
        # personId, not by container, so it's included regardless of which
        # container (PROFILE or otherwise, e.g. a Workspace DOMAIN_PROFILE) ended
        # up being used above.
        json_results[f"{container}_CONTAINER"] = {
            "profile": target,
            "play_games": player if player_results else None,
            "maps": {
                "photos": None,
                "reviews": None,
                "stats": stats
            },
            "calendar": {
                "details": calendar,
                "events": calendar_events
            } if cal_found else None
        }

    if json_file:
        import json
        from ghunt.objects.encoders import GHuntEncoder;
        with open(json_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(json_results, cls=GHuntEncoder, indent=4))
        gb.rc.print(f"\n[+] JSON output wrote to {json_file} !", style="italic")

    await as_client.aclose()
