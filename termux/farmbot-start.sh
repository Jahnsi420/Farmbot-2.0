#!/data/data/com.termux/files/usr/bin/bash
# Homescreen shortcut (Termux:Widget): connect ADB, open Clash of Clans, run the bot.
# Optional argument: number of attacks (default 20).
ATTACKS="${1:-20}"
BOT_DIR="${FARMBOT_DIR:-$HOME/farmbot/Farmbot-2.0}"
PACKAGE="com.supercell.clashofclans"

cd "$BOT_DIR" || { echo "Ordner $BOT_DIR nicht gefunden."; read -rp "Enter zum Schließen"; exit 1; }

# Already connected? Otherwise find the current wireless debugging port via mDNS.
SERIAL=$(adb devices | awk 'NR > 1 && $2 == "device" { print $1; exit }')
if [ -z "$SERIAL" ]; then
    echo "Suche Gerät über WLAN-Debugging …"
    ADDR=$(adb mdns services 2>/dev/null | awk '/_adb-tls-connect/ { print $NF; exit }')
    if [ -n "$ADDR" ] && adb connect "$ADDR" | grep -q "connected"; then
        SERIAL="$ADDR"
    fi
fi
if [ -z "$SERIAL" ]; then
    echo "Kein Gerät gefunden. Ist 'Debugging über WLAN' eingeschaltet?"
    read -rp "Enter zum Schließen"
    exit 1
fi
echo "Verbunden mit $SERIAL"

termux-wake-lock
adb -s "$SERIAL" shell monkey -p "$PACKAGE" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
python -m farmbot -s "$SERIAL" run -n "$ATTACKS"
termux-wake-unlock
read -rp "Fertig – Enter zum Schließen"
