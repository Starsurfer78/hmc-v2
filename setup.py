#!/usr/bin/env python3
import os
import sys
import asyncio
import aiohttp

# Define colors for output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def print_step(msg):
    print(f"\n{GREEN}==>{RESET} {msg}")

def print_warn(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def print_err(msg):
    print(f"{RED}❌ {msg}{RESET}")

def ask(question, default=None):
    prompt = f"{question}"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    
    val = input(prompt).strip()
    if not val and default:
        return default
    return val

async def check_jellyfin(url, api_key):
    print("   Verbinde mit Jellyfin...")
    # Remove trailing slash
    url = url.rstrip('/')
    headers = {"X-Emby-Token": api_key}
    
    try:
        async with aiohttp.ClientSession(headers=headers) as client:
            # 1. Test System Info
            async with client.get(f"{url}/System/Info", timeout=5.0) as resp:
                if resp.status == 401:
                    return False, "API Key ungültig"
                if resp.status != 200:
                    return False, f"HTTP {resp.status}"
            
            # 2. Fetch Libraries
            async with client.get(f"{url}/Library/MediaFolders", timeout=5.0) as resp_libs:
                if resp_libs.status == 200:
                    data = await resp_libs.json()
                    return True, data.get("Items", [])
            
            return True, []
            
    except aiohttp.ClientError:
        return False, "Verbindungsfehler (Server nicht erreichbar)"
    except Exception as e:
        return False, f"Fehler: {e}"

async def main():
    print(f"{GREEN}HMC v2.1 Setup Assistant{RESET}")
    print("--------------------------------")
    
    env_path = os.path.join("backend", ".env")
    
    # 1. Jellyfin Configuration
    print_step("Jellyfin Konfiguration")
    
    while True:
        jf_url = ask("Jellyfin Server URL", "http://192.168.178.X:8096")
        jf_key = ask("Jellyfin API Key")
        
        if not jf_key:
            print_err("API Key ist erforderlich!")
            continue
            
        success, result = await check_jellyfin(jf_url, jf_key)
        
        if success:
            print(f"   {GREEN}Verbindung erfolgreich!{RESET}")
            libraries = result
            break
        else:
            print_err(f"Verbindung fehlgeschlagen: {result}")
            retry = ask("Nochmal versuchen? (j/n)", "j")
            if retry.lower() != "j":
                libraries = []
                break

    # 2. Library Selection
    print_step("Bibliotheken auswählen")
    allowed_ids = []
    
    if libraries:
        selected_indices = set()
        
        while True:
            print("\nVerfügbare Bibliotheken:")
            for idx, lib in enumerate(libraries):
                mark = "[x]" if idx in selected_indices else "[ ]"
                print(f"   {mark} {idx+1}. {lib['Name']}")
            
            print("\n   [Enter] Fertig")
            
            choice = input("Nummer eingeben zum Umschalten (oder Enter für fertig): ").strip()
            
            if not choice:
                break
                
            try:
                i = int(choice) - 1
                if 0 <= i < len(libraries):
                    if i in selected_indices:
                        selected_indices.remove(i)
                    else:
                        selected_indices.add(i)
                else:
                    print_warn("Ungültige Nummer")
            except ValueError:
                print_warn("Bitte eine Zahl eingeben")
        
        for i in selected_indices:
            allowed_ids.append(libraries[i]["Id"])
            print(f"   + Aktiviert: {libraries[i]['Name']}")
    
    if not allowed_ids:
        manual = ask("Bibliotheks-IDs manuell eingeben (kommasepariert, leer lassen für keine)")
        if manual:
            allowed_ids = [x.strip() for x in manual.split(",") if x.strip()]

    # 3. User & Audio
    print_step("System Einstellungen")
    hmc_user = ask("Benutzername für dieses Gerät", "kind")
    audio_device = ask("Audio Device (ALSA)", "hw:1,0")

    # 4. Write .env
    print_step("Speichere Konfiguration...")
    
    env_content = f"""# Jellyfin
JELLYFIN_URL={jf_url}
JELLYFIN_API_KEY={jf_key}

# User Configuration
HMC_USER={hmc_user}

# Allowed Library IDs
ALLOWED_LIBRARIES={",".join(allowed_ids)}

# Audio
AUDIO_DEVICE={audio_device}
"""
    
    try:
        os.makedirs("backend", exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print(f"   {GREEN}Konfiguration gespeichert in {env_path}{RESET}")
    except Exception as e:
        print_err(f"Konnte Datei nicht schreiben: {e}")

    print("\n✅ Setup abgeschlossen! Sie können nun 'install.sh' ausführen oder den Server starten.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
