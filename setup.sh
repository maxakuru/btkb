#!/bin/bash

echo 'Updating system packages'
sudo apt-get update -y
sudo apt-get updgrade -y
sudo apt-get dist-upgrade

echo 'Installing dependencies'
sudo apt-get install python-gobject pi-bluetooth bluez bluez-tools bluez-firmware python-bluez python-dev python-pip -y

# DBUS Configuration
echo 'Configuring the dbus service'
sudo cp ./config/org.max.btkb.conf /etc/dbus-1/system.d
# sudo systemctl restart dbus

echo 'Installing BTKB'
sudo mkdir -p /usr/lib/btkb
sudo cp -TR ./client /usr/lib/btkb/client
sudo cp -TR ./server /usr/lib/btkb/server
sudo cp -TR ./start.py /usr/lib/btkb/start.py
echo 'BTKB installed to /usr/lib/btkb/'

echo 'Installing BTKB commands'
sudo cp -rf ./bin/btkb /usr/sbin
echo 'Added btkb to /usr/sbin; use `sudo btkb <KEY OR ACTION>` to write key presses to emulator'

sudo cp -rf ./bin/btkbd /usr/sbin
echo 'Added btkbd to /usr/sbin; this is the main entry for the BTKB service'

echo 'Installing BTKB service'
sudo cp -rf ./config/btkb.service /usr/lib/systemd/system/btkb.service
sudo systemctl enable btkb.service
sudo systemctl daemon-reload
sudo systemctl start btkb.service
echo 'BTKB service added to in /usr/lib/systemd/system/btkb.service'

echo ''
echo 'Done setup. Now start bluetoothctl and pair with your device. Check README for details.'
echo ''