from fifo_keymap import keymap
from time import sleep
import dbus
import signal
import os
import atexit


# Class to process and send lines of actions from a fifo
# to series of actions and keyboard HID bytestrings.
class  FifoClient():
    def __init__(self, queue, auto_release = False):
        print("Setting up FifoClient")
        
        self.queue = queue
        self.state = 'PENDING'

        self.fifo_path = '/home/pi/btkb/btkb.fifo'
        self.make_fifo()
        atexit.register(self.shutdown)

        self.bus = dbus.SystemBus()
        self.service = self.bus.get_object('org.max.btkb', "/org/max/btkb")
        self.interface = dbus.Interface(self.service, 'org.max.btkb')

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
        self.remove_fifo()

    def handle_error(self, err):
        print("FifoClient handling error: ", err, err.message, "Did not receive a reply" in err.message)
        if "Did not receive a reply" in err.message:
            print("ignoring error")
            return
        raise err

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
        print("set_modifier(): ", mod)
        if mod is None or mod == 'RESET':
            if all([ v == 0 for v in self.modifier ]):
                print("already reset!", self.modifier)
                return
            self.modifier = dict.fromkeys(self.modifier, 0)
        elif mod not in self.modifier:
            return
        else:
            self.modifier[mod] = 1 - self.modifier[mod]         

        self.modifier_byte = int(''.join([str(bit) for bit in self.modifier.values()]), 2)
        print("set modifier byte: ", self.modifier_byte)

    # Send a list of key labels
    # sample input: ['KEY_ENTER', 'KEY_CTRL']
    def send_keys(self, keys):
        print("send_keys(): ", keys, self.modifier_byte)

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
        print("do_action(): ", action)
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
        print("send_line(): ", line)

        keys_and_acts = line.split()
        for k in keys_and_acts:
            if k.startswith('ACT_'):
                self.do_action(k[4:])
            elif k.startswith('MOD_'):
                self.set_modifier(k[4:])
            else:
                self.send_keys(k.split('+'))

    # Read from the queue, looking for an update status message
    def update_state(self):
        block = True if self.status == 'PENDING' else False
        msg = self.queue.get(block=block, timeout=100)

        if msg is not None:
            if msg.topic == 'update_state':
                self.state = msg.value
            if msg.topic == 'shutdown':
                self.state = 'SHUTDOWN'

        # reset the fifo if we waited at all
        if block:
            self.remove_fifo()
            self.make_fifo()

    # Kick off main loop
    def run(self):
        while self.state is not 'SHUTDOWN':
            with open(self.fifo_path, 'r') as fifo:
                for line in fifo:
                    if self.status == 'ACTIVE':
                        self.send_line(line)
                    self.update_state()
    
    # Make the fifo, if already exists try to remove it once
    def make_fifo(self, retry=False):
        if not retry:
            print("Making FIFO")

        try :
            os.mkfifo(self.fifo_path)
        except OSError, e:
            if not retry and e.errno == 17:
                self.remove_fifo()
                return self.make_fifo(True)
            raise Exception("Could not create FIFO", e)
    
    # Remove the fifo
    def remove_fifo(self):
        print("Removing FIFO")
        os.remove(self.fifo_path)

if __name__ == "__main__":
    # Can only run as root
    # if not os.geteuid() == 0:
    #     sys.exit("Only root can run this script")

    client = FifoClient()
    signal.signal(signal.SIGINT, client.shutdown)