#!/usr/bin/env python3
import os
import sys
import asyncio
import aiohttp
import xml.etree.ElementTree as ET


def ask(question, default=None, secret=False):
    prompt = f"{question}"
    if default is not None and default != "":
        prompt += f" [{default}]"
    prompt += ": "
    val = input(prompt).strip()
    if not val and default is not None:
        return default
    return val


async def fetch_sections(plex_url: str, plex_token: str):
    url = plex_url.rstrip("/") + "/library/sections"
    params = {"X-Plex-Token": plex_token}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return False, f"HTTP {resp.status}"
            text = await resp.text()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False, "Antwort ist nicht parsebar (XML erwartet)"
    sections = []
    for directory in root.findall(".//Directory"):
        sections.append({
            "id": directory.get("key") or "",
            "name": directory.get("title") or "",
            "type": directory.get("type") or "",
        })
    return True, sections


def select_sections(sections):
    music = [s for s in sections if s.get("type") in ("artist", "music")]
    if not music:
        music = sections

    selected = set()
    while True:
        print("\nVerfuegbare Plex Bibliotheken:")
        for i, s in enumerate(music):
            mark = "[x]" if i in selected else "[ ]"
            name = s.get("name") or ""
            sid = s.get("id") or ""
            st = s.get("type") or ""
            print(f"  {mark} {i+1}. {name} (id={sid}, type={st})")
        print("\n  [Enter] Fertig")

        choice = input("Nummer zum Umschalten: ").strip()
        if not choice:
            break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(music):
                if idx in selected:
                    selected.remove(idx)
                else:
                    selected.add(idx)
        except ValueError:
            pass

    return [music[i]["id"] for i in sorted(selected) if music[i].get("id")]


async def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, "backend", ".env")

    print("Plex HMC Player Setup")
    print("---------------------")

    plex_url = ask("Plex URL", "http://192.168.178.X:32400")
    plex_token = ask("Plex Token")
    if not plex_token:
        print("PLEX_TOKEN ist erforderlich")
        sys.exit(1)

    ok, res = await fetch_sections(plex_url, plex_token)
    allowed = []
    if ok and isinstance(res, list) and res:
        allowed = select_sections(res)
    else:
        manual = ask("Section-IDs manuell eingeben (kommasepariert)", "")
        if manual:
            allowed = [x.strip() for x in manual.split(",") if x.strip()]

    audio_device = ask("Audio Device (ALSA)", "hw:1,0")
    max_volume = ask("Max. Lautstaerke (0-100)", "60")
    try:
        max_volume_int = max(0, min(100, int(max_volume)))
    except ValueError:
        max_volume_int = 60

    env_content = "\n".join([
        f"PLEX_URL={plex_url.rstrip('/')}",
        f"PLEX_TOKEN={plex_token}",
        f"PLEX_ALLOWED_SECTIONS={','.join(allowed)}",
        f"AUDIO_DEVICE={audio_device}",
        f"MAX_VOLUME={max_volume_int}",
        "",
    ])

    os.makedirs(os.path.join(base_dir, "backend"), exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(f"\nKonfiguration gespeichert: {env_path}")
    print("Naechster Schritt: uvicorn plex_hmc_player.backend.main:app --reload")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
