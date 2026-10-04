#!/data/data/com.termux/files/usr/bin/bash
# Installs the homescreen shortcuts for Termux:Widget.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.shortcuts/tasks"
cp "$HERE/farmbot-start.sh" "$HOME/.shortcuts/Farmbot starten"
cp "$HERE/farmbot-stop.sh" "$HOME/.shortcuts/tasks/Farmbot stoppen"
chmod 700 "$HOME/.shortcuts" "$HOME/.shortcuts/tasks" "$HOME/.shortcuts/Farmbot starten" "$HOME/.shortcuts/tasks/Farmbot stoppen"
echo "Verknüpfungen installiert. Jetzt das Termux:Widget auf dem Homescreen hinzufügen."
