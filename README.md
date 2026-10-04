# Farmbot 2.0

Ein Kommandozeilen-Bot, der in **Clash of Clans** automatisch farmt: Armee trainieren, Gegner suchen,
Beute prüfen, Truppen rundherum absetzen, nach Hause zurückkehren und das Ganze wiederholen.
Das Handy wird per **ADB** gesteuert. Der Bot erkennt Buttons per Bildvergleich (NumPy, optional OpenCV) und liest die Beute mit einer eigenen
Ziffernerkennung, die auf die Schrift des Spiels angelernt ist.

> ⚠️ **Achtung:** Bots verstoßen gegen die Nutzungsbedingungen von Supercell. Accounts können
> dafür dauerhaft gesperrt werden. Nutzung auf eigenes Risiko, am besten mit einem Zweit-Account.

## Voraussetzungen

1. **Python 3.10+** auf deinem PC.
2. **ADB** (Android Platform Tools): https://developer.android.com/tools/releases/platform-tools
3. Auf dem Handy: **Entwickleroptionen → USB-Debugging** aktivieren. Bei Xiaomi zusätzlich
   „USB-Debugging (Sicherheitseinstellungen)“ aktivieren, sonst funktionieren keine Taps.
4. Handy per USB anschließen und die Debugging-Anfrage bestätigen.

```bash
pip install -r requirements.txt
pip install opencv-python      # optional: schneller und Maus-Auswahl bei "capture"
python -m farmbot devices      # sollte dein Handy anzeigen
```

## Direkt auf dem Handy mit Termux

Der Bot kann auch ohne PC laufen. Er steuert das Handy dann über **Wireless Debugging**
(ab Android 11) per ADB über `localhost`.

```bash
pkg update && pkg upgrade
pkg install git python android-tools python-numpy python-pillow
pip install pyyaml                      # NICHT requirements.txt – numpy/pillow kommen aus pkg
python -c "import numpy, PIL, yaml; print('ok')"   # Test
git clone -b claude/clash-of-clans-attack-bot-yqdo1p https://github.com/Jahnsi420/Farmbot-2.0.git
cd Farmbot-2.0                          # alle farmbot-Befehle in diesem Ordner ausführen
```

ADB mit dem eigenen Handy verbinden:

1. Entwickleroptionen → **Wireless Debugging** einschalten → „Gerät mit Kopplungscode koppeln“.
2. Bildschirm teilen oder Termux im Pop-up-Fenster öffnen, dann `adb pair localhost:<Kopplungs-Port> <Code>` eingeben.
3. Danach `adb connect localhost:<Port>`. Der Port steht oben auf der Wireless-Debugging-Seite und ist nicht derselbe wie beim Koppeln.
4. `python -m farmbot devices` muss jetzt `localhost:<Port>` zeigen.

Besonderheiten:

- **OpenCV wird nicht gebraucht.** Unter Termux ist es schwer zu installieren. Ohne OpenCV ist die
  Bilderkennung etwas langsamer, reicht für den Bot aber aus.
- **Wartezeit vor dem Screenshot:** Sonst fotografiert der Bot Termux statt des Spiels. Mit
  `--delay 5` bleiben dir 5 Sekunden zum Wechseln ins Spiel, z. B. `python -m farmbot screenshot -d 5`.
- **Keine Maus-Auswahl:** Templates werden mit Pixel-Koordinaten ausgeschnitten:
  `python -m farmbot capture attack_button -d 5 --box x1,y1,x2,y2`.
  Die Koordinaten findest du über Entwickleroptionen → **Zeigerposition**. Beim Antippen stehen dann X/Y oben am Bildschirm.
- **Hintergrund-Betrieb:** Vor `run` den Befehl `termux-wake-lock` ausführen und in den Android-Einstellungen
  die Akku-Optimierung für Termux abschalten. Sonst beendet Android den Bot, sobald das Spiel im Vordergrund ist.
- Der Wireless-Debugging-Port ändert sich nach jedem Neustart oder WLAN-Wechsel. Dann `adb connect` erneut ausführen.

### Verknüpfung auf dem Homescreen

Mit der App **Termux:Widget** startest du den Bot mit einem Tipp vom Homescreen. Installiere sie aus
derselben Quelle wie Termux (F-Droid oder GitHub), sonst funktioniert sie nicht. Dann:

```bash
bash ~/farmbot/Farmbot-2.0/termux/install-shortcuts.sh
```

Lege anschließend auf dem Homescreen das Widget **Termux:Widget** an (lange auf den Homescreen tippen →
Widgets). Es zeigt zwei Einträge:

- **Farmbot starten** verbindet ADB automatisch (findet auch den neuen Port nach einem Neustart),
  öffnet Clash of Clans und startet 20 Angriffe. Das Termux-Fenster mit dem Log bleibt offen.
- **Farmbot stoppen** beendet den Bot im Hintergrund.

Ohne Widget geht es genauso mit einem Kurzbefehl in Termux:
`echo 'alias farm="bash ~/farmbot/Farmbot-2.0/termux/farmbot-start.sh"' >> ~/.bashrc`, danach `farm` (oder `farm 50`).

Beim ersten Start nach einem Neustart des Handys braucht das Skript „Debugging über WLAN“ (ist es aus,
öffnet es die Entwickleroptionen und wartet). Danach stellt es ADB auf den festen Port `localhost:5555` um:
bis zum nächsten Neustart klappt der Start dann ohne „Debugging über WLAN“ und sogar ohne WLAN.
Android erlaubt Apps nicht, Debugging selbst einzuschalten – ein Tipp bleibt also nach jedem Neustart.
Falls sich nichts öffnet: In den Android-Einstellungen bei Termux „Über anderen Apps einblenden“ erlauben.

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

Im Bild siehst du die Absetzlinien (gelb), die Absetzpunkte (rot), die Truppen-Slots (lila) und die
Beute-Bereiche (grün). Passe `deploy_lines`, `army.slots` und `loot_regions` in `config.yaml` an,
bis alles passt. Die Absetzpunkte müssen auf freiem Gras liegen, außerhalb der roten Zone um die Gebäude. Alle Werte sind relativ (0..1), funktionieren also unabhängig von der Auflösung.

**4. Beute-Erkennung testen** (auf einer gegnerischen Basis):

```bash
python -m farmbot test-loot
```

Werden falsche Zahlen erkannt, prüfe die Ausschnitte in `debug/loot_*.png` und verschiebe die Bereiche.
Die Ziffern-Vorlagen liegen in `farmbot/digit_templates/` und wurden mit `farmbot.digits.learn()` aus
echten Screenshots angelernt.

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
5. Jeder Slot wird ausgewählt und seine `count` Truppen auf den Linien aus `deploy_sides` abgesetzt:
   mit `deploy_points: 4` an 4 Punkten gleichzeitig (parallele Taps), mit `0` einzeln entlang der Linien.
   Helden-Fähigkeiten werden nach `ability_after` Sekunden aktiviert.
6. Warten auf das Kampfende, dann „Nach Hause“. Vorher wird aufgegeben, sobald in `surrender_when_idle`
   Sekunden weniger als `surrender_min_loot` Beute dazukam, spätestens aber nach `surrender_after` Sekunden.

## Entwicklung

```bash
pip install pytest
python -m pytest
```

Die Tests laufen ohne Handy (`tests/test_bot.py` simuliert ein Gerät).

| Datei               | Inhalt                                       |
|---------------------|----------------------------------------------|
| `farmbot/adb.py`    | Screenshots, Taps und App-Neustart über ADB  |
| `farmbot/imaging.py`| Bilder laden/speichern, Template-Matching    |
| `farmbot/vision.py` | Button-Erkennung                             |
| `farmbot/digits.py` | Ziffernerkennung für die Beute               |
| `farmbot/deploy.py` | Absetzpunkte entlang der Absetzlinien        |
| `farmbot/loot.py`   | Beutefilter (any / all / sum)                |
| `farmbot/bot.py`    | Ablaufsteuerung                              |
| `farmbot/cli.py`    | Kommandozeilenbefehle                        |
