# Script to start both server and FifoClient
from server.btkb_server import BTKbService
from client.fifo_client import FifoClient
from dbus.mainloop.glib import DBusGMainLoop
import multiprocessing
from os import geteuid
import sys
import signal 
from time import sleep

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def start_server():
    try:
        DBusGMainLoop(set_as_default=True)
        BTKbService()
        Gtk.main()
    finally:
        return

if __name__ == "__main__":
    # Can only run as root
    if not geteuid() == 0:
        sys.exit("Only root can run this script")

    # TODO: parse args to get auto_release
    auto_release = True

    server = multiprocessing.Process(target=start_server)
    server.start()

    sleep(1)

    fifo = multiprocessing.Process(target=FifoClient)
    fifo.start()

    def shutdown(sig_num, frame):
        server.terminate()
        fifo.terminate()

        server.join()
        fifo.join()

    signal.signal(signal.SIGINT, shutdown)

    # fifo = FifoClient(auto_release)