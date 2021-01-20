#!/bin/bash

if [ ! -f config.ini ]; then
    echo "config.ini does not exist! Copy, rename, and configure config.ini.example"
    exit 1
fi

echo 'Updating system packages'
sudo apt-get update -y
sudo apt-get updgrade -y
sudo apt-get dist-upgrade

echo 'Installing dependencies'
sudo apt-get install python-gobject pi-bluetooth bluez bluez-tools bluez-firmware python-bluez python-dev python-pip -y

# DBUS Configuration
echo 'Configuring the dbus service'
sudo cp ./etc/org.max.btkb.conf /etc/dbus-1/system.d

echo 'Installing BTKB'
sudo mkdir -p /usr/lib/btkb
sudo cp -TR ./client /usr/lib/btkb/client
sudo cp -TR ./server /usr/lib/btkb/server
sudo cp -TR ./start.py /usr/lib/btkb/start.py

if [ -f /usr/lib/btkb/config.ini ]; then
    sudo cp -TR ./config.ini /usr/lib/btkb/config.ini
else
    echo "Config already found in destination, ignoring."
fi

echo 'BTKB installed to /usr/lib/btkb/'

echo 'Installing BTKB commands'
sudo cp -rf ./bin/btkb /usr/sbin
echo 'Added btkb to /usr/sbin; use `sudo btkb <KEY OR ACTION>` to write key presses to emulator'

sudo cp -rf ./bin/btkbd /usr/sbin
echo 'Added btkbd to /usr/sbin; this is the main entry for the daemon'

echo 'Installing BTKB daemon'
sudo cp -rf ./etc/btkbd.service /usr/lib/systemd/system/btkbd.service
sudo systemctl enable btkbd.service
sudo systemctl daemon-reload
sudo systemctl start btkbd.service
echo 'BTKB service added to in /usr/lib/systemd/system/btkb.service'

echo ''
echo 'Done setup. Now start bluetoothctl and pair with your device. Check README for details.'
echo ''