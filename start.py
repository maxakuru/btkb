# Script to start both server and FifoClient
from server.btkb_server import BTKbService
from client.fifo_client import FifoClient
from dbus.mainloop.glib import DBusGMainLoop
import multiprocessing
from os import geteuid
import sys
import signal 
from time import sleep
import configparser

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def start_server(queue):
    try:
        DBusGMainLoop(set_as_default=True)
        BTKbService(queue)
        Gtk.main()
    finally:
        return

def read_config():
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
    except Exception as e:
        print "Failed to read config.ini"
        raise e

    return {
        'auto_release': config['Service'].getboolean('AutoRelease', fallback=False),
        'device_mac': config['Service'].getstring('DeviceMac', fallback='CHANGE_ME'),
        'device_uuid': config['Service'].getstring('DeviceUUID', fallback='00001124-0000-1000-8000-00805f9b34fb'),
        'device_name': config['Service'].getstring('DeviceName', fallback='btkb'),
        'device_class': config['Service'].getstring('DeviceClass', fallback='0x002540'),
        'port_control': config['Service'].getint('PortControl', fallback=17),
        'port_interrupt': config['Service'].getstring('PortInterrupt', fallback=19),

        'fifo_path': config['FifoClient'].getstring('Path', fallback='/tmp/btkb.fifo'),
        'fifo_owner_gid': config['FifoClient'].getint('OwnerGID', fallback=None),
        'fifo_owner_uid': config['FifoClient'].getint('OwnerUID', fallback=None)
    }

if __name__ == "__main__":
    # Can only run as root
    if not geteuid() == 0:
        sys.exit("Only root can run this script")

    c = read_config()

    # Queue to pass data from FIFO to service
    queue = multiprocessing.Queue()

    # Start service process
    server = multiprocessing.Process(
        target=start_server, 
        args=(
            queue, 
            c['device_mac'], 
            c['device_name'], 
            c['device_uuid'], 
            c['auto_release'], 
            c['device_class'], 
            c['port_control'], 
            c['port_interrupt']
        )
    )
    server.start()

    # Start FIFO client process
    fifo = multiprocessing.Process(
        target=FifoClient, 
        args=(
            queue,
            c['fifo_path'],
            c['fifo_owner_uid'],
            c['fifo_owner_gid']
        )
    )
    fifo.start()

    def shutdown(sig_num, frame):
        server.terminate()
        fifo.terminate()

        server.join()
        fifo.join()

    signal.signal(signal.SIGINT, shutdown)

    # fifo = FifoClient(auto_release)