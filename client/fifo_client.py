
from __future__ import print_function

from fifo_keymap import keymap
from time import sleep
import dbus
import signal
import os
import atexit
import Queue
import multiprocessing as mp
from threading import Thread
import select
import subprocess

# Reads from a fifo using a thread, puts lines onto a queue
class FifoReader():
    def __init__(self, fifo_path='/tmp/btkb.fifo', owner_uid=None, owner_gid=None):
        print("[BTKB:FIFO] FifoReader setting up with owner (uid, gid): ", (owner_uid, owner_gid))

        self.fifo_path = fifo_path
        self.queue = mp.Queue()
        self.make_fifo(owner_uid, owner_gid)
        self.proc = None

    def make_fifo(self, uid=None, gid=None, retry=False):
        self.remove_fifo()

        if not retry:
            print("[BTKB:FIFO] Making fifo at path: " + self.fifo_path)
            if uid is not None:
                print("[BTKB:FIFO] Setting UID: " + str(uid))
                os.setuid(uid)
            if gid is not None:
                print("[BTKB:FIFO] Setting GID: " + str(gid))
                os.setgid(gid)

        try:
            os.mkfifo(self.fifo_path)
        except OSError, e:
            if not retry and e.errno == 17:
                self.remove_fifo()
                return self.make_fifo(uid, gid, True)
            raise Exception("[BTKB:FIFO] Could not make fifo", e)
    
    def run(self):
        self.proc = mp.Process(target=self.read_loop)
        self.proc.start()

    # Repeatedly read from fifo
    def read_loop(self):
        while True:
            with open(self.fifo_path, 'r') as fifo:
                for data in fifo:
                    self.queue.put_nowait(data)

        print("[BTKB:FIFO] after queue run loop")

    def empty(self):
        return self.queue.empty()

    # Get a line from the fifo
    # If timeout elapses with no data, signal to update state
    def get_line(self, timeout=100):
        # print("[BTKB:FIFO] get_line() ", timeout)
        # TODO: notify of needing state update
        try:
            return self.queue.get(True, timeout), False
        except Queue.Empty:
            return None, True

        if self.queue.empty():
            return None, False
        return self.queue.get(block=False, timeout=timeout), False

     # Remove the fifo
    def remove_fifo(self):
        print("[BTKB:FIFO] Removing FIFO")
        try:
            os.remove(self.fifo_path)
        except OSError as e:
            if e.errno != 2:
                raise e
    
    def shutdown(self):
        if self.proc is not None:
            self.proc.terminate()
            self.proc.join()
        self.remove_fifo()

    def flush(self):
        while not self.queue.empty():
            self.queue.get()

# Class to process and send lines of actions from a fifo
# to series of actions and keyboard HID bytestrings.
class  FifoClient():
    def __init__(self, in_queue, fifo_path='/tmp/btkb.fifo', owner_uid=None, owner_gid=None):
        print("[BTKB:FIFO] Setting up FifoClient")
        
        self.queue = in_queue
        # state of BTKB service, BT connection
        # PENDING - before dbus is ready
        # DISCONNECTED - dbus is ready, but before BT device is connected or after it has disconnected
        # CONNECTED - device connected, ready to read from fifo and push commands to device
        # SHUTDOWN - received message to shutdown, exit loop
        self.state = 'PENDING'

        # TODO: Allow sleep time to be modified by messages on FIFO
        self.control_sleep = 0.5

        # FIFO setup
        self.fifo_reader = FifoReader(fifo_path, owner_uid, owner_gid)
        self.fifo_reader.run()

        self.bus = None
        self.service = None
        self.interface = None

        self.modifier = {
            'RIGHTMETA': 0,
            'RIGHTALT': 0,
            'RIGHTSHIFT': 0,
            'RIGHTCTRL': 0,
            'LEFTMETA': 0,
            'LEFTALT': 0,
            'LEFTSHIFT': 0,
            'LEFTCTRL': 0
        }
        self.modifier_byte = 0x00

        self.run()

    def shutdown(self):
        self.fifo_reader.shutdown()

    def handle_error(self, err):
        print("[BTKB:FIFO] Handling error: ", err)
        if "Did not receive a reply" in err.message:
            self.update_state()
            return
        raise err

    def init_dbus(self):
        print("[BTKB:FIFO] Set up dbus interface")
        self.bus = dbus.SystemBus()
        self.service = self.bus.get_object('org.max.btkb', "/org/max/btkb")
        self.interface = dbus.Interface(self.service, 'org.max.btkb')

    # Toggle persistent modifier
    # Note: MOD_ is stripped before reaching this fn
    # Valid labels for modifiers: 
    # MOD_RIGHTMETA - right GUI/windows key
    # MOD_RIGHTALT
    # MOD_RIGHTSHIFT
    # MOD_RIGHTCTRL
    # MOD_LEFTMETA - left GUI/windows key
    # MOD_LEFTALT
    # MOD_LEFTSHIFT
    # MOD_LEFTCTRL
    # MOD_RESET
    def set_modifier(self, mod = None):
        # print("[BTKB:FIFO] set_modifier(): ", mod)
        if mod is None or mod == 'RESET':
            if all([ v == 0 for v in self.modifier ]):
                return
            self.modifier = dict.fromkeys(self.modifier, 0)
        elif mod not in self.modifier:
            return
        else:
            self.modifier[mod] = 1 - self.modifier[mod]         

        self.modifier_byte = int(''.join([str(bit) for bit in self.modifier.values()]), 2)
        # print("[BTKB:FIFO] set modifier byte: ", self.modifier_byte)

    # Send a list of key labels
    # sample input: ['KEY_ENTER', 'KEY_CTRL']
    def send_keys(self, keys):
        #print("[BTKB:FIFO] send_keys(): ", keys, self.modifier_byte)
        cmd = []
        cmd.append(0xA1)
        cmd.append(0x01)
        cmd.append(self.modifier_byte)
        cmd.append(0x00)

        count=0
        for key in keys:
            if(count>5):
                break
            if key not in keymap:
                continue
            cmd.append(keymap[key])
            count+=1

        try:
            self.interface.send_bytes(cmd)
        except Exception as e:
            self.handle_error(e)

    # Do some action, like releasing all keys or holding for a while
    # Valid actions:
    # ACT_HOLD_<# seconds>
    # ACT_RELEASE
    def do_action(self, action):
        #print("[BTKB:FIFO] do_action(): ", action)
        if action == 'RELEASE':
            try:
                self.interface.release_keys()
            except Exception as e:
                self.handle_error(e)

        elif action.startswith('HOLD'):
            d = 0
            try:
                parts = action.split("_")
                d = float(parts[1]) if len(parts) > 1 else 0
            except:
                pass
            sleep(d)
    
    # Send a line of keys and actions
    # Sample 1: KEY_ENTER ACT_HOLD_1 ACT_RELEASE
    # =>: "press down enter key", "hold for 1 second", "release all keys"
    # Sample 2: KEY_CTRL+KEY_ALT+KEY_DELETE ACT_RELEASE
    # =>: "press down control alt and delete", "release all keys"
    # Sample 3: KEY_CTRL KEY_ALT KEY_DELETE
    # =>: "press down control alt and delete" (if auto_release is true, similar as sample 2)
    def send_line(self, line):
        #print("[BTKB:FIFO] send_line(): ", line)
        keys_and_acts = line.split()

        for k in keys_and_acts:
            if k.startswith('ACT_'):
                self.do_action(k[4:])
            elif k.startswith('MOD_'):
                self.set_modifier(k[4:])
            else:
                self.send_keys(k.split('+'))

    # Read from the queue, looking for an update status message
    def update_state(self, block=False, timeout=0):
        #print("[BTKB:FIFO] update_state: ", block, self.state)
        try:
            msg = self.queue.get(block=block, timeout=timeout)
            if msg is None:
                return
            if msg['topic'] == 'update_state':
                self.state = msg['value']
            if msg['topic'] == 'shutdown':
                self.state = 'SHUTDOWN'
        except Queue.Empty:
            pass

    # Kick off main loop
    def run(self):
        # Initial setup loop, waits for PENDING to become ACTIVE
        # This is done with no sleep since it should be quick
        while self.state == 'PENDING':
            self.update_state(block=True, timeout=0.1)
            if self.state != 'PENDING':
                break

        # dbus service is ready
        self.init_dbus()

        while self.state != 'SHUTDOWN':
            # Now wait until a connection is made
            while self.state == 'DISCONNECTED':
                self.update_state(block=True, timeout=0.5)
                sleep(self.control_sleep)            

            # Reset the fifo in case a bunch of command were queued up,
            # don't want them all to replay once the connection is made
            self.fifo_reader.flush()

            while self.state == 'CONNECTED':
                line, update = self.fifo_reader.get_line()
                if line is not None:
                    self.send_line(line)
                if update:
                    self.update_state(False)
        self.shutdown()

# TODO: read from config
if __name__ == "__main__":
    client = FifoClient()
    signal.signal(signal.SIGINT, client.shutdown)