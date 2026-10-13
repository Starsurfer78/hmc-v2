# HMC Media Player (Home Assistant Custom Component)

Bindet ein [HMC](../../README.md)-Gerät als echte `media_player`-Entität in Home Assistant ein.

## Warum diese Komponente nötig ist

Home Assistants eingebaute MQTT-Integration kennt kein Discovery-Schema für
`media_player` – anders als z.B. für `sensor`, `switch` oder `climate`. Ein
HMC-Gerät kann sich deshalb nicht rein über MQTT-Discovery als Media-Player
in HA anmelden. Diese Komponente übernimmt genau das: Sie liest die von HMC
ohnehin veröffentlichten MQTT-Topics (`hmc/{device_id}/state`,
`hmc/{device_id}/command`, `hmc/{device_id}/availability`) und stellt daraus
eine reguläre `MediaPlayerEntity` bereit.

## Installation

**Über HACS** (empfohlen):
1. HACS → Drei-Punkte-Menü → *Custom repositories*
2. Repository-URL dieses Projekts eintragen, Kategorie *Integration*
3. "HMC Media Player" installieren, Home Assistant neu starten

**Manuell:**
1. Diesen Ordner (`custom_components/hmc_media_player/`) nach
   `<home-assistant-config>/custom_components/hmc_media_player/` kopieren
2. Home Assistant neu starten

## Einrichtung

1. Voraussetzung: Die MQTT-Integration ist in Home Assistant bereits
   eingerichtet und mit demselben Broker verbunden, den auch HMC in seiner
   `backend/.env` (`MQTT_BROKER`) verwendet.
2. **Einstellungen → Geräte & Dienste → Integration hinzufügen → "HMC Media Player"**
3. Geräte-ID eintragen – muss exakt der `MQTT_DEVICE_ID` aus der `backend/.env`
   des HMC-Geräts entsprechen (z.B. `hmc_kinderzimmer`)
4. Anzeigename vergeben

Für mehrere HMC-Player im Haus die Integration mehrfach hinzufügen (eine
Geräte-ID pro HMC-Instanz).

## Durchsagen (TTS) und Medien-URLs

Ab Version 1.1.0 unterstützt die Entität `media_player.play_media` inkl.
Durchsagen. Beispiel:

```yaml
action: tts.speak
target:
  entity_id: tts.google_translate_de_de   # bzw. eure TTS-Engine
data:
  media_player_entity_id: media_player.hmc_kinderzimmer
  message: "Das Abendessen ist fertig!"
```

- `tts.speak` sendet automatisch als **Durchsage**: HMC unterbricht die
  laufende Wiedergabe, spielt die Ansage und setzt danach an derselben Stelle
  fort (auch im Pause-Zustand). Die Warteschlange bleibt erhalten.
- `media_player.play_media` ohne `announce` spielt die URL stattdessen als
  normale Wiedergabe ab und ersetzt die Warteschlange.
- Die Lautstärke ist die aktuelle HMC-Lautstärke (begrenzt durch die
  Max-Lautstärke aus dem HMC-Admin-Panel).
- HA übergibt HMC eine absolute URL zu seinem TTS-Proxy. Dafür muss unter
  **Einstellungen → System → Netzwerk** eine *lokale* Home-Assistant-URL
  eingetragen sein, die der HMC-Pi erreicht (z.B. `http://192.168.178.10:8123`).
  Sonst kann HMC die Ansage nicht laden — im HMC-Journal erscheint dann
  `Durchsage konnte nicht abgespielt werden`.
