#!/bin/sh
if [ `id -u` != 0 ]; then
    echo "This script must be run as root"
    exit 1
fi

SD_UNIT_PATH="/etc/systemd/system"

CMD="$1"

if [ "$CMD" = "install" ]; then
    echo "Copying service unit files..."
    cp gauge.service $SD_UNIT_PATH
    cp gauge-cv.service $SD_UNIT_PATH
    cp gauge-webapp.service $SD_UNIT_PATH
    cp gauge-display.service $SD_UNIT_PATH
    cp gauge-hass.service $SD_UNIT_PATH
    echo "Enabling services..."
    systemctl enable gauge
    systemctl enable gauge-cv
    systemctl enable gauge-webapp
    systemctl enable gauge-display
    systemctl enable gauge-hass
    echo "Services installed and enabled.  To start services, you can run:"
    echo "sudo systemctl start gauge"
fi

if [ "$CMD" = "remove" ]; then
    echo "Stopping services..."
    systemctl stop gauge
    systemctl stop gauge-cv
    systemctl stop gauge-webapp
    systemctl stop gauge-display
    systemctl stop gauge-hass
    echo "Disabling services..."
    systemctl disable gauge
    systemctl disable gauge-cv
    systemctl disable gauge-webapp
    systemctl disable gauge-display
    systemctl disable gauge-hass
    echo "Removing service unit files..."
    rm -f $SD_UNIT_PATH/gauge.service
    rm -f $SD_UNIT_PATH/gauge-cv.service
    rm -f $SD_UNIT_PATH/gauge-webapp.service
    rm -f $SD_UNIT_PATH/gauge-display.service
    rm -f $SD_UNIT_PATH/gauge-hass.service
    echo "Removed systemd services."
    exit 1
fi



echo "Must specify command: install or remove"




