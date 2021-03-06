#!/usr/bin/python2

#
# Bluetooth keyboard emulator DBUS Service
# 
# Adapted from 
# https://github.com/yaptb/BlogCode/blob/master/btkeyboard/server/btk_server.py
#
#

from __future__ import absolute_import, print_function

from optparse import OptionParser, make_option
import os
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
from bluetooth import *
from dbus.mainloop.glib import DBusGMainLoop
import xml.etree.ElementTree as ET

# Define a bluez 5 profile object for our keyboard
class BTKbBluezProfile(dbus.service.Object):
    fd = -1

    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)

    # For in_signature and out_signature,
    # see: https://dbus.freedesktop.org/doc/dbus-python/tutorial.html#data-types
    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        print("[BTKB:Bluez] Release")
        mainloop.quit()

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Cancel(self):
        print("[BTKB:Bluez] Cancel")

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, path, fd, properties):
        self.fd = fd.take()
        print("[BTKB:Bluez] NewConnection(%s, %d)" % (path, self.fd))
        for key in properties.keys():
            if key == "Version" or key == "Features":
                print("  %s = 0x%04x" % (key, properties[key]))
            else:
                print("  %s = %s" % (key, properties[key]))

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, path):
        print("[BTKB:Bluez] RequestDisconnection(%s)" % (path))
        if (self.fd > 0):
            os.close(self.fd)
            self.fd = -1


# Create a bluetooth device to emulate a HID keyboard, 
# advertise an SDP record using our bluez profile class.
class BTKbDevice():  
    PROFILE_DBUS_PATH = "/bluez/max/btkb_profile" # dbus path of the bluez profile we will create
    SDP_RECORD_PATH = os.path.dirname(os.path.abspath(__file__)) + '/sdp_record.xml' # path to SDP record to load
 
    def __init__(self, bd_addr, name, uuid, dev_class = '0x002540', p_control = 17, p_interrupt = 19):
        print("[BTKB] Setting up BT device")
        print("     bd_addr: ", bd_addr)
        print("     name: ", name)
        print("     uuid: ", uuid)
        print("     class: ", dev_class)
        print("     control port: ", p_control)
        print("     interrupt port: ", p_interrupt)

        if bd_addr == 'CHANGE_ME':
            raise Exception("Bluetooth device address not configured! See config.ini.")

        self.device_addr = bd_addr
        self.device_uuid = uuid
        self.device_name = name
        self.device_class = dev_class
        self.p_ctrl = p_control
        self.p_intr = p_interrupt

        self.init_bt_device()
        self.init_bluez_profile()
                    

    # Configure the bluetooth hardware device
    def init_bt_device(self):
        print("[BTKB] Configuring for name " + self.device_name + ", and class: " + self.device_class)

        # Set the device class to a keybord and set the name
        # Device class 0x002540 is a HID keyboard
        os.system("hciconfig hcio class " + self.device_class)
        os.system("hciconfig hcio name " + self.device_name)

        # Make the device discoverable
        os.system("hciconfig hcio piscan")


    # Set up a bluez profile to advertise device capabilities from a loaded service record.
    def init_bluez_profile(self):
        print("[BTKB] Configuring Bluez profile")

        #setup profile options
        service_record = self.read_sdp_service_record()

        opts = {
            "ServiceRecord": service_record,
            "Role": "server",
            "RequireAuthentication": False,
            "RequireAuthorization": False
        }

        # Retrieve a proxy for the bluez profile interface
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        profile = BTKbBluezProfile(bus, BTKbDevice.PROFILE_DBUS_PATH)
        manager.RegisterProfile(BTKbDevice.PROFILE_DBUS_PATH, self.device_uuid, opts)

        print("[BTKB] Profile registered")


    # Read and return an sdp record from a file
    def read_sdp_service_record(self):
        print("[BTKB] Reading service record from path: ", BTKbDevice.SDP_RECORD_PATH)

        try:
            fh = open(BTKbDevice.SDP_RECORD_PATH, "r")
        except:
            sys.exit("Could not open the SDP record. Exiting...")

        return fh.read()   



    # Listen for incoming client connections.
    # Ideally this would be handled by the Bluez 5 profile,
    # but that didn't seem to work.
    def listen(self):
        print("[BTKB] listen()")

        self.scontrol = BluetoothSocket(L2CAP)
        self.sinterrupt = BluetoothSocket(L2CAP)

        # Bind these sockets to a port - port zero to select next available
        self.scontrol.bind((str(self.device_addr), int(self.p_ctrl)))
        self.sinterrupt.bind((str(self.device_addr), int(self.p_intr)))

        # Start listening on the server sockets
        print("[BTKB] Waiting for connections: "+ self.device_addr, self.p_ctrl, self.p_intr)
        self.scontrol.listen(1) # Limit of 1 connection
        self.sinterrupt.listen(1)

        self.ccontrol, cinfo = self.scontrol.accept()
        print ("[BTKB] Got a connection on the control channel from " + cinfo[0])

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print ("[BTKB] Got a connection on the interrupt channel from " + cinfo[0])

    def reconnect(self):
        print("[BTKB] reconnect()")

        self.ccontrol, cinfo = self.scontrol.accept()
        print ("[BTKB] Reconnected to control channel " + cinfo[0])

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print ("[BTKB] Reconnected to interrupt channel " + cinfo[0])

    def close(self):
        print("[BTKB] close()")

        self.scontrol.close()
        self.sinterrupt.close()

    # Send a string to the bluetooth host machine
    def send_string(self, message):
        self.cinterrupt.send(message)



# Define a dbus service that emulates a bluetooth keyboard.
class  BTKbService(dbus.service.Object):

    def __init__(self, out_queue, shutdown_flag, bd_addr, name, uuid, auto_release=False, dev_class='0x002540', p_control = 17, p_interrupt = 19):
        print("[BTKB] Setting up service")
        self.queue = out_queue

        self.auto_release = auto_release

        # Det up as a dbus service
        bus_name = dbus.service.BusName("org.max.btkb", bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, "/org/max/btkb")

        self.update_state("DISCONNECTED")

        # Create and setup our device
        self.device = BTKbDevice(bd_addr, name, uuid, dev_class, p_control, p_interrupt)

        # Start listening for connections
        self.device.listen()

        # Mark state as active after connection received
        self.update_state("CONNECTED")

    # Let client know that the state of the service has changed
    def update_state(self, state):
        #print("[BTKB] update_state(): ", state)
        if self.queue is not None:
            self.queue.put({
                'topic': 'update_state',
                'value': state
            }, False)
        

    # Handle exceptions, sometimes by restarting the listening process
    def handle_error(self, err):
        # connection reset by peer or transport error
        if "104" in err.message or "107" in err.message:
            print("[BTKB] Closing and listening again...")
            self.update_state("DISCONNECTED")
            self.device.reconnect()
            self.update_state("CONNECTED")
        else:
            self.update_state("SHUTDOWN")
            raise err

    @dbus.service.method('org.freedesktop.DBus.Introspectable', out_signature='s')
    def Introspect(self):
        intro_path = os.path.dirname(os.path.abspath(__file__)) + '/org.max.btkb.introspection'
        print("[BTKB] Introspecting from file: ", intro_path)
        return ET.tostring(ET.parse(intro_path).getroot(), encoding='utf8', method='xml')

    # Send a string, probably a string of bytes
    @dbus.service.method('org.max.btkb', in_signature='ay')
    def send_bytes(self, b):
        # print("[BTKB] send_bytes() ", b)
        try:
            bs = ''.join([chr(v) for v in b])
            self.device.send_string(bs)
        except Exception as e:
            self.handle_error(e)

    # Send a string, probably a string of bytes
    @dbus.service.method('org.max.btkb', in_signature='')
    def release_keys(self):
        try:
            self.device.send_string(chr(0xA1)+chr(0x01)+chr(0x00))
        except Exception as e:
            self.handle_error(e)

    # Send a list of bytes
    @dbus.service.method('org.max.btkb', in_signature='yayb')
    def send_keys(self, modifier_byte, keys, auto_release=None):
        if auto_release is None:
            auto_release = self.auto_release

        cmd_str=""
        cmd_str+=chr(0xA1)
        cmd_str+=chr(0x01)
        cmd_str+=chr(modifier_byte)
        cmd_str+=chr(0x00)

        count=0
        for key in keys:
            if(count > 5):
                break
            cmd_str += chr(key)
            count += 1

        # send the keys
        try:
            self.device.send_string(cmd_str)
            # mark input as finished if specified
            if release:
                self.device.send_string(chr(0xA1)+chr(0x01)+chr(0x00))
        except Exception as e:
            self.handle_error(e)

    def close(self):
        try:
            self.device.close()
        except:
            pass

# Run the server individually, can be done without using start.py if you want
# TODO: read from config
if __name__ == "__main__":
    # Can only run as root
    if not os.geteuid() == 0:
        sys.exit("[BTKB] Only root can run this script")

    # DBusGMainLoop(set_as_default=True)
    service = BTKbService()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        service.close()