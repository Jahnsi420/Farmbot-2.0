# Farmbot 2.0

Ein Kommandozeilen-Bot, der in **Clash of Clans** automatisch farmt: Armee trainieren, Gegner suchen,
Beute prüfen, Truppen rundherum absetzen, nach Hause zurückkehren und das Ganze wiederholen.
Das Handy wird per **ADB** gesteuert. Der Bot erkennt Buttons per Bildvergleich (OpenCV) und liest die Beute per OCR (Tesseract).

> ⚠️ **Achtung:** Bots verstoßen gegen die Nutzungsbedingungen von Supercell. Accounts können
> dafür dauerhaft gesperrt werden. Nutzung auf eigenes Risiko, am besten mit einem Zweit-Account.

## Voraussetzungen

1. **Python 3.10+** auf deinem PC.
2. **ADB** (Android Platform Tools): https://developer.android.com/tools/releases/platform-tools
3. **Tesseract OCR**:
   Windows: Installer von https://github.com/UB-Mannheim/tesseract/wiki (danach den Ordner in den PATH aufnehmen).
   Linux: `sudo apt install tesseract-ocr`. macOS: `brew install tesseract`.
4. Auf dem Handy: **Entwickleroptionen → USB-Debugging** aktivieren. Bei Xiaomi zusätzlich
   „USB-Debugging (Sicherheitseinstellungen)“ aktivieren, sonst funktionieren keine Taps.
5. Handy per USB anschließen und die Debugging-Anfrage bestätigen.

```bash
pip install -r requirements.txt
python -m farmbot devices      # sollte dein Handy anzeigen
```

## Direkt auf dem Handy mit Termux

Der Bot kann auch ohne PC laufen. Er steuert das Handy dann über **Wireless Debugging**
(ab Android 11) per ADB über `localhost`.

```bash
pkg update
pkg install x11-repo                    # OpenCV liegt im X11-Repository
pkg install git python android-tools tesseract python-numpy python-pillow opencv-python
pip install pyyaml pytesseract          # NICHT requirements.txt – opencv kommt aus pkg
python -c "import cv2; print(cv2.__version__)"   # Test
git clone -b claude/clash-of-clans-attack-bot-yqdo1p https://github.com/Jahnsi420/Farmbot-2.0.git
cd Farmbot-2.0                          # alle farmbot-Befehle in diesem Ordner ausführen
```

ADB mit dem eigenen Handy verbinden:

1. Entwickleroptionen → **Wireless Debugging** einschalten → „Gerät mit Kopplungscode koppeln“.
2. Bildschirm teilen oder Termux im Pop-up-Fenster öffnen, dann `adb pair localhost:<Kopplungs-Port> <Code>` eingeben.
3. Danach `adb connect localhost:<Port>`. Der Port steht oben auf der Wireless-Debugging-Seite und ist nicht derselbe wie beim Koppeln.
4. `python -m farmbot devices` muss jetzt `localhost:<Port>` zeigen.

Besonderheiten:

- **Wartezeit vor dem Screenshot:** Sonst fotografiert der Bot Termux statt des Spiels. Mit
  `--delay 5` bleiben dir 5 Sekunden zum Wechseln ins Spiel, z. B. `python -m farmbot screenshot -d 5`.
- **Keine Maus-Auswahl:** Templates werden mit Pixel-Koordinaten ausgeschnitten:
  `python -m farmbot capture attack_button -d 5 --box x1,y1,x2,y2`.
  Die Koordinaten findest du über Entwickleroptionen → **Zeigerposition**. Beim Antippen stehen dann X/Y oben am Bildschirm.
- **Hintergrund-Betrieb:** Vor `run` den Befehl `termux-wake-lock` ausführen und in den Android-Einstellungen
  die Akku-Optimierung für Termux abschalten. Sonst beendet Android den Bot, sobald das Spiel im Vordergrund ist.
- Der Wireless-Debugging-Port ändert sich nach jedem Neustart oder WLAN-Wechsel. Dann `adb connect` erneut ausführen.

## Einrichtung (einmalig)

**1. Konfiguration anlegen**

```bash
cp config.example.yaml config.yaml
```

**2. Templates aufnehmen.** Öffne im Spiel den passenden Bildschirm und markiere den Button mit der Maus:

```bash
python -m farmbot capture attack_button   # im Dorf
python -m farmbot capture find_match      # im Angriffsmenü
python -m farmbot capture next_button     # bei einer gegnerischen Basis
python -m farmbot capture return_home     # auf dem Kampfende-Bildschirm
```

Welche Templates es gibt, steht in [`templates/README.md`](templates/README.md).

**3. Positionen kalibrieren.** Starte eine Gegnersuche bis zu einer Basis und führe dann aus:

```bash
python -m farmbot show-deploy      # schreibt debug/calibration.png
```

Im Bild siehst du die Spielfeld-Raute (gelb), die Absetzpunkte (rot), die Truppen-Slots (lila) und die
Beute-Bereiche (grün). Passe `map_diamond`, `army.slots[].pos` und `loot_regions` in `config.yaml` an,
bis alles passt. Alle Werte sind relativ (0..1), funktionieren also unabhängig von der Auflösung.

**4. Beute-Erkennung testen** (auf einer gegnerischen Basis):

```bash
python -m farmbot test-loot
```

Werden falsche Zahlen erkannt, prüfe die Ausschnitte in `debug/loot_*.png` und verschiebe die Bereiche.

## Starten

```bash
python -m farmbot run                  # nutzt session.max_attacks aus der Konfig
python -m farmbot run -n 3 --debug     # 3 Angriffe, Screenshots bei Problemen in debug/
```

Stoppen mit **Strg+C**. Erkennt der Bot einen Bildschirm nicht, startet er das Spiel neu. Nach 3 Fehlern
in Folge bricht er ab.

## Ablauf eines Angriffs

1. Warten, bis das Dorf zu sehen ist (`attack_button`).
2. Optional die Armee neu trainieren: die Templates aus `training.sequence` werden nacheinander angetippt.
3. Angriff → Gegner suchen.
4. Beute lesen. Erfüllt sie `search` nicht, wird „Weiter“ getippt (das kostet Gold!).
   Nach `max_skips` Versuchen wird trotzdem angegriffen.
5. Jeder Slot wird ausgewählt und seine `count` Truppen gleichmäßig auf den `deploy_sides` abgesetzt.
   Helden-Fähigkeiten werden nach `ability_after` Sekunden aktiviert.
6. Warten auf das Kampfende (oder Aufgeben nach `surrender_after`), dann „Nach Hause“.

## Entwicklung

```bash
pip install pytest
python -m pytest
```

Die Tests laufen ohne Handy (`tests/test_bot.py` simuliert ein Gerät).

| Datei               | Inhalt                                       |
|---------------------|----------------------------------------------|
| `farmbot/adb.py`    | Screenshots, Taps und App-Neustart über ADB  |
| `farmbot/vision.py` | Template-Matching und OCR der Beute          |
| `farmbot/deploy.py` | Absetzpunkte entlang der Kartenraute         |
| `farmbot/loot.py`   | Beutefilter (any / all / sum)                |
| `farmbot/bot.py`    | Ablaufsteuerung                              |
| `farmbot/cli.py`    | Kommandozeilenbefehle                        |
