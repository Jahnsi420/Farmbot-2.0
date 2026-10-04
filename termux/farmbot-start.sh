#!/data/data/com.termux/files/usr/bin/bash
# Start the bot from Termux (alias "farm" or Termux:Widget): connect ADB, open Clash of Clans, run.
# Optional argument: number of attacks (default 20).
ATTACKS="${1:-20}"
BOT_DIR="${FARMBOT_DIR:-$HOME/farmbot/Farmbot-2.0}"
PACKAGE="com.supercell.clashofclans"
LOCAL="localhost:5555"  # fixed port that survives Wi-Fi changes until the next reboot

cd "$BOT_DIR" || { echo "Ordner $BOT_DIR nicht gefunden."; read -rp "Enter zum Schließen"; exit 1; }

first_device() { adb devices | awk 'NR > 1 && $2 == "device" { print $1; exit }'; }

# Wait up to $2 seconds until $1 is connected and authorized.
wait_device() {
    for _ in $(seq "$2"); do
        [ "$(adb -s "$1" get-state 2>/dev/null)" = "device" ] && return 0
        sleep 1
    done
    return 1
}

# Current wireless debugging address (ip:port) announced via mDNS, if it is switched on.
wireless_address() { adb mdns services 2>/dev/null | awk '/_adb-tls-connect/ { print $NF; exit }'; }

SERIAL=$(first_device)

# 1. Fixed port from an earlier run (works without Wi-Fi debugging until the phone reboots).
if [ -z "$SERIAL" ]; then
    adb connect "$LOCAL" >/dev/null 2>&1
    wait_device "$LOCAL" 3 && SERIAL="$LOCAL"
fi

# 2. Wi-Fi debugging; if it is off, open the developer options and wait for the user.
if [ -z "$SERIAL" ]; then
    for attempt in 1 2 3; do
        ADDR=$(wireless_address)
        if [ -n "$ADDR" ]; then
            adb connect "$ADDR" >/dev/null 2>&1
            wait_device "$ADDR" 5 && SERIAL="$ADDR" && break
        fi
        [ "$attempt" = 3 ] && break
        echo "Debugging über WLAN ist aus. Ich öffne die Entwickleroptionen:"
        echo "  → 'Debugging über WLAN' einschalten, dann zurück zu Termux und Enter drücken."
        am start -a android.settings.APPLICATION_DEVELOPMENT_SETTINGS >/dev/null 2>&1
        read -rp "Enter, sobald es eingeschaltet ist … "
        sleep 2  # give mDNS a moment to announce the port
    done
fi

if [ -z "$SERIAL" ]; then
    echo "Kein Gerät gefunden. Ist 'Debugging über WLAN' eingeschaltet und das WLAN verbunden?"
    read -rp "Enter zum Schließen"
    exit 1
fi

# 3. Switch to the fixed port, so the next start needs no Wi-Fi debugging until a reboot.
if [ "$SERIAL" != "$LOCAL" ]; then
    echo "Richte festen Port ein (gilt bis zum nächsten Neustart) …"
    adb -s "$SERIAL" tcpip 5555 >/dev/null 2>&1
    sleep 2
    adb connect "$LOCAL" >/dev/null 2>&1
    echo "Falls 'USB-Debugging zulassen?' erscheint: 'Immer zulassen' anhaken und 'Zulassen' tippen."
    if wait_device "$LOCAL" 30; then
        SERIAL="$LOCAL"
    else
        # keep using Wi-Fi debugging this time
        adb connect "$SERIAL" >/dev/null 2>&1
        wait_device "$SERIAL" 10 || { echo "Verbindung verloren."; read -rp "Enter zum Schließen"; exit 1; }
    fi
fi
echo "Verbunden mit $SERIAL"

termux-wake-lock
adb -s "$SERIAL" shell monkey -p "$PACKAGE" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
python -m farmbot -s "$SERIAL" run -n "$ATTACKS"
termux-wake-unlock
read -rp "Fertig – Enter zum Schließen"
