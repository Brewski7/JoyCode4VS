#!/bin/bash

set -e

APT_PACKAGES=(
    python3
    python3-pip
    python3-pyqt5
    python3-matplotlib
    python3-pyqt5.qtwebkit
    python3-evdev
    python3-pygame
    python3-can
    python3-serial
    can-utils
    net-tools
)

PIP_ONLY_PACKAGES=(
    cantools
    pynput
)

echo "Updating package index..."
sudo apt update

echo "Installing system packages..."
for pkg in "${APT_PACKAGES[@]}"; do
    echo "Installing $pkg..."
    sudo apt install -y "$pkg"
done

echo "Installing pip-only packages..."
for pkg in "${PIP_ONLY_PACKAGES[@]}"; do
    echo "Installing $pkg via pip..."
    sudo python3 -m pip install --break-system-packages "$pkg"
done

echo "Checking for DBC files..."
if [ ! -f ezkontrol/EZkontrol_CAN.dbc ]; then
    echo "ERROR: DBC file 'EZkontrol_CAN.dbc' not found."
    exit 1
fi
if [ ! -f votol-em150/Roam_CAN.dbc ]; then
    echo "ERROR: DBC file 'EZkontrol_CAN_Debug.dbc' not found."
    exit 1
fi

echo "Setting up CAN-HAT driver..."
if [ ! -d "lg-master" ]; then
    wget https://github.com/joan2937/lg/archive/master.zip
    unzip master.zip
    cd lg-master
    sudo make install
    cd ..
fi

CONFIG_FILE="/boot/firmware/config.txt"
echo "Configuring /boot/firmware/config.txt for MCP2515..."
CONFIG_BLOCK="dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000"

if ! grep -q "dtoverlay=mcp2515-can0" "$CONFIG_FILE"; then
    echo "$CONFIG_BLOCK" | sudo tee -a "$CONFIG_FILE"
else
    echo "Overlay already configured."
fi

# Create desktop shortcut for launching visualizers
DESKTOP_SHORTCUT="$HOME/Desktop/BikeOnTheWall.desktop"
RUN_SCRIPT="$(realpath "$(dirname "$0")/run_viz.sh")"
ICON_PATH="$(realpath "$(dirname "$0")/icon.png")"

echo "Creating desktop shortcut at $DESKTOP_SHORTCUT..."

cat > "$DESKTOP_SHORTCUT" <<EOF
[Desktop Entry]
Name=BikeOnTheWall
Comment=Launches roam_viz and ezkontrol_viz in separate terminals
Exec=$RUN_SCRIPT
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Utility;
EOF

chmod +x "$DESKTOP_SHORTCUT"

echo "Desktop shortcut created! You can double-click it to launch both visualizers."

echo "Setup complete! Please reboot the Raspberry Pi to apply CAN-HAT configuration."
echo "Would you like to reboot now? [y/N]"
read -r reboot_answer
if [[ "$reboot_answer" == "y" || "$reboot_answer" == "Y" ]]; then
    sudo reboot
else
    echo "You can reboot later using: sudo reboot"
    echo "Once rebooted, run the visualizer with:"
    echo "    python3 ezkontrol_viz_v2.py"
fi

