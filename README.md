# btkb

A bluetooth HID keyboard emulator service and FIFO client.

### Goal
The purpose of this project was to create a way to relay messages to control an Amazon Firestick quickly (since it's for a TV remote). It's quite possible this isn't the fastest way, but it's certainly faster than using `adb shell keyinput` or `sendevent`.

I'm currently using this on a Raspberry Pi Zero W to dispatch commands received from IR signals on a TV remote. I went with the FIFO passthrough because the remote's protocol is DirecTV, and either I'm too stupid or lazy to figure out any other way to use it (ie. ir-keytable) than "raw codes" with [LIRCD](https://www.lirc.org/html/lircd.html). Ultimately, the `btkb` command in this repo is used by `irexec`. This setup still allows for some IR codes to be "exchanged" - for example, specific buttons on a remote can lead to `irexec` emitting different IR codes for devices that have no other way to commmunicate. This story has little to do with the actual code here, but I hope you enjoyed it.


### Setup
1. Get the repo
```sh
git clone git@github.com:maxakuru/btkb.git
```

2. Enable bluetooth if needed
```sh
sudo hciconfig hcio up
```

3. Copy `config.ini.example` and rename to `config.ini`

4. Configure `config.ini` how you like, at least the device address is needed
>> Note: To get the bluetooth device address, use `sudo hciconfig hci0 -a` and look for `BD Address`.

5. Run the setup script (or set it up however you want)
```sh
/bin/bash setup.sh
```

6. Pair your device
```sh
sudo /usr/bin/bluetoothctl
```
>> Then
```sh
agent on
default-agent
pairable on
discoverable on
```
>> And leave this terminal running.

Find your device in the bluetooth device list, pair, accept
Back in the terminal, accept the pairing code with `yes`.

7. Send keystrokes via fifo
A convenience script is installed with the setup script, but really it just pushes whatever the arguments you provide into a fifo.
This fifo is then read, line by line, by the FifoClient, converted into HID bytestrings and sent to the connected device.
The fifo is owned by uid/gid 1000, but depending on step 2, you may need `sudo`.

#### Sample commands
Press down "enter":
```sh
btkb KEY_ENTER
```

Press down "enter", release all keys:
```sh
btkb KEY_ENTER ACT_RELEASE
```

Press down "enter", hold it for a second, release:
```sh
btkb KEY_ENTER ACT_HOLD_1 ACT_RELEASE
```

Left ctrl + esc, then release keys and unhold "ctrl" modifier:
```sh
btkb MOD_LEFTCTRL KEY_ESC ACT_RELEASE MOD_RESET
```
>> Note: this works the same as the `KEY_HOMESCREEN` event on Firestick (and maybe other Android TV devices)


#### Alternative use
Write directly to the fifo, if you want:
```sh
echo "KEY_ENTER ACT_RELEASE" >> /tmp/btkb.fifo
```
>> Note: This requires using the same user as configured in `config.ini`

#### Credits
Not sure who this is, but [very helpful!](http://yetanotherpointlesstechblog.blogspot.com/2016/04/emulating-bluetooth-keyboard-with.html)

[AnesBenmerzoug/BluetoothHID](https://github.com/AnesBenmerzoug/Bluetooth_HID)