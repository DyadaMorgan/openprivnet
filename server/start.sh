#!/bin/bash

# Get the absolute path to this script's directory
DIR="$(cd "$(dirname "$0")" && pwd)"

# Command to run the server and wait for ANY key press before closing
RUN_CMD="bash -c '$DIR/server; echo; echo \"Press any key to exit...\"; read -n1 -s'"

# Try to launch in an available terminal
if command -v gnome-terminal &>/dev/null; then
    gnome-terminal -- bash -c "$RUN_CMD"
elif command -v xfce4-terminal &>/dev/null; then
    xfce4-terminal --command="$RUN_CMD"
elif command -v konsole &>/dev/null; then
    konsole -e bash -c "$RUN_CMD"
elif command -v xterm &>/dev/null; then
    xterm -e bash -c "$RUN_CMD"
else
    echo "No supported terminal found. Running in the current shell."
    eval "$RUN_CMD"
fi

