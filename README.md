# Simrad Shipmate RS8300 – ATIS umprogrammieren

Die ATIS-Kennung eines **Simrad Shipmate RS8300** (UKW-Binnenfunk, Baujahr um 1999) lässt sich am Handset nur ein einziges Mal eingeben. Danach ist sie gesperrt, und laut Anleitung darf nur der Fachhändler sie ändern. Ein Händler-Tool dafür ist nicht mehr aufzutreiben.

Dieses Repository zeigt, wie man die ATIS mit einem **Arduino Uno** und einer **SOIC-8-Klemme** direkt im EEPROM des Geräts ausliest und neu schreibt, ohne zu löten.

*English summary: The ATIS ID of a Simrad Shipmate RS8300 is stored as BCD in the NM93C46 Microwire EEPROM (U18) at word addresses 0x2E, 0x2F and the high byte of 0x3D. There is no checksum. An Arduino sketch and a Python tool to back up, read and write the ATIS are included.*

> [!IMPORTANT]
> **Rechtliches:** Ein Funkgerät darf nur mit der ATIS senden, die die zuständige Behörde dem Schiff zugeteilt hat (in Deutschland die Bundesnetzagentur). Die Tools sind dafür gedacht, ein Gerät auf die **eigene, zugeteilte** Kennung umzustellen, etwa nach einem Eignerwechsel oder beim Einbau eines gebrauchten Geräts.
>
> Alles auf eigenes Risiko. Vor jeder Änderung ein Backup machen; das Tool erledigt das automatisch.

## Ergebnis in Kürze

| ATIS-Ziffern | Speicherort im NM93C46 (64 × 16 Bit) | Beispiel `9211234567` |
|---|---|---|
| 1–4 | Wort **0x2E**, BCD | `9211` |
| 5–8 | Wort **0x2F**, BCD | `2345` |
| 9–10 | Wort **0x3D**, **oberes Byte**, BCD | `67xx` (unteres Byte nicht ändern) |

- **Keine Prüfsumme.** Die Firmware übernimmt geänderte Werte beim nächsten Einschalten.
- Am Handset zeigt **`E ↑ 88 E`** die Ziffern 1–5 und **`E ↑ 87 E`** die Ziffern 6–10. Eingegeben wird die ATIS mit `E ↑ 82 E` / `E ↑ 83 E`, solange sie noch nicht gesperrt ist.
- Oberes Byte von Wort 0x3C = Squelch-Einstellung. Wort 0x30 hat nichts mit der ATIS zu tun.
- **MMSI:** Ein RS8300 ohne DSC (keine Distress-Taste) kennt keine MMSI. `E ↑ 97/98 E` und `E ↑ 92/93 E` melden dann `error`. Das ist normal.

Ermittelt an einem Gerät mit Firmware-Aufkleber „017“ auf dem 87C51, durch gezielte Schreibtests und Ablesen am Handset. Andere Firmware-Stände könnten abweichen, deshalb vorher `dump` und `show` prüfen.

## Hardware

- Arduino Uno oder Nano (5 V)
- SOIC-8-Testklemme mit Adapter auf Steckbrett oder Jumperkabel
- Optional: Multimeter

Im Hauptgerät stecken:

| Bauteil | Typ | Bedeutung |
|---|---|---|
| U13 | 87C51FB, PLCC-44, gesockelt | Prozessor mit Firmware |
| **U18** | **NM93C46**, SO-8 | 1-kBit-Microwire-EEPROM, ORG auf VCC, also 64 × 16 Bit |

U18 sitzt neben dem PLCC-Sockel des Prozessors.

## Verdrahtung

| NM93C46 | Signal | Arduino |
|---|---|---|
| 1 | CS | D10 |
| 2 | SK | D13 |
| 3 | DI | D11 |
| 4 | DO | D12 |
| 5 | GND | GND |
| 8 | VCC | **5V** |
| 6 / 7 | ORG / NC | nicht anschließen |

## Ablauf

> [!WARNING]
> **Ohne Prozessor lässt sich das Gerät nicht einschalten.** Eingeschaltet wird es übers Handset, und das wertet der Prozessor aus. Der EEPROM bekommt seinen Strom deshalb vom Arduino.
>
> Dabei versorgt der Arduino die ganze 5-V-Schiene der Platine mit. Deshalb vorher **unbedingt die 12 V abklemmen** und **den 87C51 aus dem Sockel ziehen**. Sonst läuft der Prozessor mit und kommt dem Arduino auf dem Bus in die Quere.

1. **12 V abklemmen**, Gerät öffnen, **87C51 ziehen**. Lage von Pin 1 merken.
2. Den Widerstand zwischen EEPROM Pin 8 und Pin 5 messen und einen Kurzschluss ausschließen.
3. Klemme aufsetzen (Pin 1 beachten) und wie oben verdrahten.
4. Sketch flashen:
   ```sh
   pio run -e uno -t upload        # oder: -e nano
   ```
   Alternativ `src/mw93c46.ino` mit der Arduino IDE öffnen und hochladen.
5. Python-Abhängigkeit installieren: `pip install pyserial`
6. **Backup** anlegen und aktuelle ATIS anzeigen:
   ```sh
   python3 atis.py dump
   ```
   Den Dump unter `dumps/` gut aufheben. Er enthält auch die Abgleichwerte des Geräts.
7. **Neue ATIS schreiben.** Vorher wird automatisch ein Backup angelegt, danach wird kontrolliert gelesen:
   ```sh
   python3 atis.py set 9211234567
   ```
8. Arduino-5V abklemmen, Klemme abnehmen, 87C51 wieder einsetzen, 12 V anschließen.
9. Übers Handset einschalten und mit `E ↑ 88 E` und `E ↑ 87 E` kontrollieren.

Zurück zum alten Stand:
```sh
python3 atis.py restore dumps/nm93c46_<datum>_dump.bin
```

## Werkzeuge

### `src/mw93c46.ino`: Arduino-Sketch
Microwire-Treiber für 93C46 im 64×16-Modus. Bedienung über die serielle Schnittstelle (115200 Baud, Zeilenende `\n`, alle Werte hex):

| Befehl | Funktion |
|---|---|
| `d` | ganzen EEPROM ausgeben |
| `r <adr>` | ein Wort lesen |
| `w <adr> <wort>` | ein Wort schreiben, danach zurücklesen und prüfen |

Der Sketch verwendet weder ERASE noch ERAL. So funktioniert er auch mit Ersatztypen wie dem AK93C45A, die diese Befehle nicht kennen.

### `atis.py`: Python-Tool
| Befehl | Funktion |
|---|---|
| `dump` | dreimal lesen, vergleichen, Backup speichern |
| `show` | gespeicherte ATIS anzeigen |
| `set <atis>` | Backup anlegen, ATIS schreiben, kontrollieren |
| `restore <datei>` | Backup zurückschreiben (nur die Worte, die abweichen) |

Optional: `--port /dev/ttyACM0`. Ohne Angabe nimmt das Tool die erste gefundene serielle Schnittstelle.

## Fehlersuche

- **Der erste Lesevorgang nach dem Anschließen liefert in 0x00–0x0F nur `0000`:** Das ist ein bekannter Effekt beim ersten Zugriff. `atis.py` verwirft deshalb den ersten Dump und liest danach dreimal zum Vergleich.
- **Die Dumps unterscheiden sich, oder alle Worte sind `FFFF` oder `0000`:** Die Klemme sitzt schlecht, Pin 1 ist verdreht oder Pin 8 hat keine 5 V.
- **Am Handset erscheint `error` bei 82/83:** Die ATIS ist gesperrt. Genau dafür ist dieses Repository da.

## Quellen

- Bedienungsanleitung RS8300/8400: <https://rigpix.com/marine/simrad-shipmate_rs8300-8400_manual.pdf>
- Schaltplan RS8300/8400 (peel.dk): <https://www.peel.dk/Shipmate/Equipment/Shipmate%20RS8300-8400%20-%20Marine%20VHF%20Radiotelephone%20(Schematics,%20bad%20quality%20scan).pdf>
- Datenblatt AK93C45A (Ersatztyp): <https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/2521/AK93C45A_55A_64A_75A.pdf>

## Lizenz

[MIT](LICENSE)
