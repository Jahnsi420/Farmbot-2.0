#!/data/data/com.termux/files/usr/bin/bash
# Homescreen shortcut (Termux:Widget, runs in the background): stop the bot.
pkill -INT -f "python -m farmbot" && echo "Farmbot gestoppt."
termux-wake-unlock
