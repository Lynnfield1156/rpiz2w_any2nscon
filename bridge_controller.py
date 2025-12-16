#!/usr/bin/env python3
import evdev
import struct
import time
import sys
import os
import select
import binascii

# Constants
GADGET_PATH = "/dev/hidg0"

# Pro Controller Button Map (Bitmask for Report ID 0x30)
# Byte 0 (Buttons)
BTN_Y       = 0x01
BTN_B       = 0x02
BTN_A       = 0x04
BTN_X       = 0x08
BTN_L       = 0x10
BTN_R       = 0x20
BTN_ZL      = 0x40
BTN_ZR      = 0x80

# Byte 1 (Buttons)
BTN_MINUS   = 0x01
BTN_PLUS    = 0x02
BTN_LCLICK  = 0x04
BTN_RCLICK  = 0x08
BTN_HOME    = 0x10
BTN_CAPTURE = 0x20

# Byte 2 (Hat)
HAT_TOP          = 0x00
HAT_TOP_RIGHT    = 0x01
HAT_RIGHT        = 0x02
HAT_BOTTOM_RIGHT = 0x03
HAT_BOTTOM       = 0x04
HAT_BOTTOM_LEFT  = 0x05
HAT_LEFT         = 0x06
HAT_TOP_LEFT     = 0x07
HAT_CENTER       = 0x08

# SPI Response Data (Hardcoded Calibration/ID)
# Derived from NXIC / mzyy94
SPI_CALIB_DATA = {
    b'\x00\x60': bytes.fromhex('ffffffffffffffffffffffffffffffff'), # Serial
    b'\x50\x60': bytes.fromhex('bc1142 75a928 ffffff ffffff ff'), # Color (Splatoon 2 Neon Green/Pink)
    b'\x80\x60': bytes.fromhex('50fd0000c60f0f30619630f3d41454411554c7799c333663'), # Factory Sensor/Stick
    b'\x98\x60': bytes.fromhex('0f30619630f3d41454411554c7799c333663'), # Factory Stick 2
    b'\x3d\x60': bytes.fromhex('ba156211b87f29065bffe77e0e36569e8560ff323232ffffff'), # Factory Config 2
    b'\x10\x80': bytes.fromhex('ffffffffffffffffffffffffffffffffffffffffffffb2a1'), # User Stick Calib
    b'\x28\x80': bytes.fromhex('beff3e00f001004000400040fefffeff0800e73be73be73b'), # User 6-Axis Calib
}

MAC_ADDR = "D4F0578D7423" # Dummy MAC

def map_hat(x, y):
    if x == 0 and y == -1: return HAT_TOP
    if x == 1 and y == -1: return HAT_TOP_RIGHT
    if x == 1 and y == 0:  return HAT_RIGHT
    if x == 1 and y == 1:  return HAT_BOTTOM_RIGHT
    if x == 0 and y == 1:  return HAT_BOTTOM
    if x == -1 and y == 1: return HAT_BOTTOM_LEFT
    if x == -1 and y == 0: return HAT_LEFT
    if x == -1 and y == -1: return HAT_TOP_LEFT
    return HAT_CENTER

class ProControllerBridge:
    def __init__(self, gadget_path):
        self.gadget_path = gadget_path
        self.gadget_fd = -1
        self.packet_counter = 0
        self.mac_bytes = bytes.fromhex(MAC_ADDR)[::-1] # Little Endian for some fields, Big for others? NXIC uses standard.
        
        # State
        self.btns = 0
        self.hat = HAT_CENTER
        self.lx = 0x800 # 12-bit Center (0-4095) => 2048
        self.ly = 0x800
        self.rx = 0x800
        self.ry = 0x800
        
        # Safe Button Access
        self.BTN_SHARE = getattr(evdev.ecodes, 'BTN_SHARE', getattr(evdev.ecodes, 'BTN_SELECT', 314))
        self.BTN_OPTIONS = getattr(evdev.ecodes, 'BTN_OPTIONS', getattr(evdev.ecodes, 'BTN_START', 315))
        self.BTN_MODE = getattr(evdev.ecodes, 'BTN_MODE', 316)

    def open_gadget(self):
        try:
            self.gadget_fd = os.open(self.gadget_path, os.O_RDWR | os.O_NONBLOCK)
            print(f"Opened {self.gadget_path}")
        except FileNotFoundError:
            print(f"Error: {self.gadget_path} not found.")
            sys.exit(1)

    def send_report(self, report):
        try:
            os.write(self.gadget_fd, report)
        except BlockingIOError:
            pass
        except Exception as e:
             if isinstance(e, OSError) and e.errno in [108, 32]: # Disconnected
                 pass
             else:
                 print(f"Write Error: {e}")

    def create_input_report_0x30(self):
        # 0x30 Input Report Structure (Standard)
        # Byte 0: 0x30 (ID)
        # Byte 1: Timer (Counter)
        # Byte 2: Battery/Connection (0x91 = Charging/USB?) NXIC uses 00 80 00... initial_input='81008000...'
        # Let's match NXIC initial_input header: 81 00 80 00 ... ?
        # NXIC 'buf' sent to response(0x30...):
        # response() adds [0x30, counter].
        # buf starts with 00 00 ...
        # NXIC initial_input = '81008000f8d77a22c87b0c' -> 11 bytes.
        # But 'buf' in input_response starts with buf[2]=0x00...
        
        # Re-reading NXIC:
        # initial_input = '81 00 80 00 f8 d7 7a 22 c8 7b 0c'
        # response(0x30, counter, buf) -> buffer becomes [0x30, counter] + buf
        # Payload:
        # 0x30
        # Counter
        # 81 (Byte 0 of buf) -> Battery/Conn?
        # 00 (Byte 1) -> Buttons Low? -> NXIC modifies buf[1] for keys.
        # 80 (Byte 2) -> Buttons High? -> NXIC modifies buf[2] for Home/Plus.
        # 00 (Byte 3) -> Sticks/Hat? -> NXIC modifies buf[3] for Sticks/Hat.
        # ...
        
        self.packet_counter = (self.packet_counter + 1) & 0xFF
        
        # Buttons
        b0 = self.btns & 0xFF
        b1 = (self.btns >> 8) & 0xFF
        b2 = (self.btns >> 16) & 0xFF # Hat + Sticks shared?
        
        # NXIC Logic Mapping:
        # buf[1] (Buttons Low): Y=01, X=02, B=04, A=08, R=40, ZR=80
        # buf[2] (Buttons Mid): Minus=01, Plus=02, LClick=08, Home=10, Capture=20
        # buf[3] (Buttons High/Stick/Hat): DDown=01, DUp=02, DRight=04, DLeft=08, L=40, ZL=80
        # Stick encoding is 12-bit packed into bytes 4-9.
        
        # Re-pack correctly based on my BTN constants (which match NXIC roughly)
        # My constants: Y=01, B=02, A=04, X=08... differ slightly from NXIC?
        # NXIC: L='A' key -> buf[1] |= 0x08. So A is 0x08.
        # Standard Pro Con:
        # Byte 2 (0-based from 0x30, so Byte 0 of data): Y(01), B(02), A(04), X(08), L(10), R(20), ZL(40), ZR(80)
        # Byte 3: Minus(01), Plus(02), L3(04), R3(08), Home(10), Cap(20)
        # Byte 4: Stick data starts...
        
        # Let's use Standard Pro Controller Layout used by NintendoSwitchControlLibrary:
        # 0x30, Counter, Battery(0x81), 
        # Buttons[0] (Y B A X L R ZL ZR)
        # Buttons[1] (Min Pls L3 R3 Hom Cap)
        # Buttons[2] (Hat? Stick?)
        
        # Stick Data (12-bit):
        # Byte 0: LX (Low 8)
        # Byte 1: LX (High 4) | LY (Low 4)
        # Byte 2: LY (High 8)
        # Byte 3: RX (Low 8) ...
        
        # Build Packet
        msg = bytearray(64)
        msg[0] = 0x30
        msg[1] = self.packet_counter
        msg[2] = 0x81 # Battery High/USB
        
        # Buttons
        msg[3] = self.btns & 0xFF
        msg[4] = (self.btns >> 8) & 0xFF
        msg[5] = (self.btns >> 16) & 0xFF # Hat usually here
        
        # Hat (Nibble 0? or Byte 5?)
        # Standard: Byte 5 is "Wired/Vendor" + Hat?
        # NXIC uses logic:
        # stick_l_flg = lh | (lv << 12) ...
        # buf[4], buf[5], buf[6] ...
        # This matches 12-bit packing.
        
        # 12-bit packing
        # LX (12), LY (12), RX (12), RY (12)
        # Bytes needed: 1.5 * 4 = 6 bytes.
        
        l_packed = self.lx | (self.ly << 12)
        r_packed = self.rx | (self.ry << 12)
        
        msg[6] = l_packed & 0xFF
        msg[7] = (l_packed >> 8) & 0xFF
        msg[8] = (l_packed >> 16) & 0xFF
        
        msg[9] = r_packed & 0xFF
        msg[10] = (r_packed >> 8) & 0xFF
        msg[11] = (r_packed >> 16) & 0xFF
        
        # 6-Axis Data (Bytes 12-47)
        # Fill with Center values (00 80 usually? or signed 0?)
        # Pro Con 6-axis is 16-bit signed. 
        # 0 is still, but gravity applies.
        # Just leave as 0 for now (flat).
        
        return msg

    def handle_output_report(self, data):
        # data[0] is Report ID
        cmd = data[0]
        subcmd = data[1] if len(data) > 1 else 0
        
        if cmd == 0x80:
            # Status Request
            if subcmd == 0x01: # Handshake 1
                 self.send_response(0x81, 0x01, bytes.fromhex('0003')) # + MAC?
                 # NXIC: response(0x81, data[1], bytes.fromhex('0003' + mac_addr))
                 payload = bytes.fromhex('0003') + bytes.fromhex(MAC_ADDR)
                 self.send_response(0x81, 0x01, payload)
                 
            elif subcmd == 0x02: # Handshake 2
                 self.send_response(0x81, 0x02, b'')
                 
            elif subcmd == 0x04: # Handshake 3? (Start Inputs)
                 # Just acknowledge, keepalive loop handles 0x30 sending
                 pass
                 
        elif cmd == 0x01: # Subcommand/Rumble
             # Rumble data is at data[2:10], Subcmd at data[10]
             if len(data) > 10:
                 real_subcmd = data[10]
                 self.handle_subcommand(real_subcmd, data[11:])
                 
    def handle_subcommand(self, subcmd, data):
        # Acknowledge Subcommand (ID 0x21)
        # Structure: 0x21, Counter, InputReport(11+36?), Ack(Subcmd), ReplyData
        
        reply_data = b''
        
        if subcmd == 0x01: # Manual Pairing
            reply_data = b'\x03'
            
        elif subcmd == 0x02: # Device Info
            # Firmware 3.73, Pro Con, MAC...
            # 03 49 03 02 [MAC Reversed?] 03 02
            # NXIC: '03490302' + mac_addr[::-1] + '0302'
            # Note: NXIC mac_addr string slice [::-1]? No, it's string.
            # My MAC_ADDR is string.
            # bytes.fromhex(MAC_ADDR)[::-1]
            mac_rev = bytes.fromhex(MAC_ADDR)[::-1]
            reply_data = bytes.fromhex('03490302') + mac_rev + bytes.fromhex('0302')
            
        elif subcmd == 0x04: # Trigger Elapsed
            pass # Empty reply OK
            
        elif subcmd == 0x10: # SPI Read
            # Addr is first 2 bytes of data (Little Endian?)
            # NXIC data[11:13] is addr
            addr = data[0:2]
            length = data[4] if len(data) > 4 else 0
            
            # Find data
            if addr in SPI_CALIB_DATA:
                 read_data = SPI_CALIB_DATA[addr]
            else:
                 read_data = b'\xFF' * length # Default FF
                 
            # Reply: Addr(2) + Len(2? No 00 00) + Len + Data
            # NXIC: buf = addr + 00 00 + len + data
            reply_data = addr + b'\x00\x00' + bytes([len(read_data)]) + read_data
            
        elif subcmd == 0x21: # NFC Config
            reply_data = bytes.fromhex('0100ff0003000501')
            
        elif subcmd == 0x40: # IMU Config
            reply_data = b'' # Ack
            
        elif subcmd == 0x48: # Vibration Config
            reply_data = b'' # Ack
        
        elif subcmd == 0x30: # Player Lights
            # Reply: Byte w/ bitmask of lights?
            # Standard reply is just ACK with echo subcommand?
            # Reply should contain Subcmd + Data.
            # If no data needed, just empty.
            reply_data = b'\x01' # 1?
        
        # Send Reply (ID 0x21)
        self.send_subcmd_reply(subcmd, reply_data)

    def send_response(self, id, subcmd, data):
        # Generic Response Packet
        msg = bytearray(64)
        msg[0] = id
        msg[1] = subcmd
        if data:
            msg[2:2+len(data)] = data
        self.send_report(msg)

    def send_subcmd_reply(self, subcmd, data):
        # 0x21 Input Report + Ack
        # 0x21, Counter, [Standard Input Report ~47 bytes?], AckCmd, Data
        
        msg = bytearray(64)
        msg[0] = 0x21
        msg[1] = self.packet_counter
        
        # Standard Input Data (Battery, Buttons, Sticks, 6-Axis)
        # Just use current state logic roughly
        msg[2] = 0x81
        msg[3] = self.btns & 0xFF
        msg[4] = (self.btns >> 8) & 0xFF
        msg[5] = (self.btns >> 16) & 0xFF
        
        l_packed = self.lx | (self.ly << 12)
        r_packed = self.rx | (self.ry << 12)
        msg[6] = l_packed & 0xFF
        msg[7] = (l_packed >> 8) & 0xFF
        msg[8] = (l_packed >> 16) & 0xFF
        msg[9] = r_packed & 0xFF
        msg[10] = (r_packed >> 8) & 0xFF
        msg[11] = (r_packed >> 16) & 0xFF
        
        # 6-Axis (12-47) - Zeros
        
        # ACK Format @ Byte 13 (0-indexed? No wait)
        # 0x21 (0)
        # Timer (1)
        # Bat/Btn/Sticks/6Axis (2-47) -> ~46 bytes?
        # Ack Subcmd is usually at Byte 13 or 14?
        # Standard: 
        # Header (2) + Bat(1) + Btn(3) + Stick(6) + Vib(1) + 6Axis(36) = 49 bytes data?
        # Wait, 6Axis is 36 bytes.
        # 1+3+6 = 10 bytes basic data.
        # Ack starts after basic data + vibration report?
        
        # Looking at NXIC uart_response:
        # buf = initial_input (11 bytes: 81 00 ... sticks)
        # buf.extend([code, subcmd]) -> code is output report ID? No.
        # NXIC uart_response(0x21, counter, buf)
        # buf starts with initial_input (11 bytes).
        # buf.extend([ack_code, subcmd])
        # buf.extend(data)
        
        # So structure:
        # 0x21
        # Counter
        # Input Data (11 bytes: 81 00 ...)
        # Code (Ack Result? 0x80/0x82...)
        # Subcmd (Echo)
        # Data
        
        # msg[2:13] is Input (11 bytes).
        msg[13] = 0x80 # ACK? NXIC uses arg 'code'. Successful ack is usually 0x80 or 0x81?
                       # NXIC calls uart_response(0x82...) for Device Info.
                       # I should check standard.
                       # 0x82 seems to be Device Info ACK. 0x80 is simple ACK?
        
        # Let's infer from subcmd logic above:
        # Pair -> 0x81
        # Info -> 0x82
        # Trigger -> 0x83
        # SPI -> 0x90
        # NFC -> 0xA0
        
        ack_code = 0x80
        if subcmd == 0x01: ack_code = 0x81
        elif subcmd == 0x02: ack_code = 0x82
        elif subcmd == 0x04: ack_code = 0x83
        elif subcmd == 0x10: ack_code = 0x90
        elif subcmd == 0x21: ack_code = 0xA0
        
        msg[13] = ack_code
        msg[14] = subcmd
        if data:
            msg[15:15+len(data)] = data
            
        self.send_report(msg)

    def run(self):
        print("Waiting for DS4...")
        ds4 = None
        while ds4 is None:
            for path in evdev.list_devices():
                dev = evdev.InputDevice(path)
                if "Sony" in dev.name or "Wireless Controller" in dev.name:
                    if "Touchpad" not in dev.name:
                        ds4 = dev
                        print(f"Found {dev.name}")
                        break
            if not ds4: time.sleep(1)
            
        self.open_gadget()
        print("Pro Controller Emulation Running...")
        
        while True:
            start = time.time()
            
            # Read Gadget (for Handshake)
            r, _, _ = select.select([self.gadget_fd, ds4], [], [], 0)
            
            if self.gadget_fd in r:
                try:
                    data = os.read(self.gadget_fd, 64)
                    if data:
                         self.handle_output_report(data)
                except:
                    pass
                    
            if ds4 in r:
                for event in ds4.read():
                    self.process_ds4_event(event)

            # Send Keepalive (Input Report 0x30) ~60Hz
            # Only send 0x30 if we are NOT replying to a subcommand in this frame?
            # Actually standard is to strictly interval 0x30 approx 15ms.
            # Replies (0x21) replace 0x30 for that frame or are sent immediately?
            # For simplicity, just send 0x30 every loop for now.
            # Real Pro Con sends 0x30 continuously.
            
            self.send_report(self.create_input_report_0x30())

            # Sleep remainder
            elapsed = time.time() - start
            if elapsed < 0.015:
                time.sleep(0.015 - elapsed)

    def process_ds4_event(self, event):
        if event.type == evdev.ecodes.EV_KEY:
            val = event.value
            if event.code == evdev.ecodes.BTN_SOUTH: # B
                if val: self.btns |= BTN_B
                else:   self.btns &= ~BTN_B
            elif event.code == evdev.ecodes.BTN_EAST: # A
                if val: self.btns |= BTN_A
                else:   self.btns &= ~BTN_A
            elif event.code == evdev.ecodes.BTN_NORTH: # X
                if val: self.btns |= BTN_X
                else:   self.btns &= ~BTN_X
            elif event.code == evdev.ecodes.BTN_WEST: # Y
                if val: self.btns |= BTN_Y
                else:   self.btns &= ~BTN_Y
            elif event.code == evdev.ecodes.BTN_TL: # L
                if val: self.btns |= BTN_L
                else:   self.btns &= ~BTN_L
            elif event.code == evdev.ecodes.BTN_TR: # R
                if val: self.btns |= BTN_R
                else:   self.btns &= ~BTN_R
            elif event.code == evdev.ecodes.BTN_TL2: # ZL
                if val: self.btns |= BTN_ZL
                else:   self.btns &= ~BTN_ZL
            elif event.code == evdev.ecodes.BTN_TR2: # ZR
                if val: self.btns |= BTN_ZR
                else:   self.btns &= ~BTN_ZR
            elif event.code == self.BTN_SHARE: # Minus
                if val: self.btns |= (BTN_MINUS << 8)
                else:   self.btns &= ~(BTN_MINUS << 8)
            elif event.code == self.BTN_OPTIONS: # Plus
                if val: self.btns |= (BTN_PLUS << 8)
                else:   self.btns &= ~(BTN_PLUS << 8)
            elif event.code == self.BTN_MODE: # Home
                if val: self.btns |= (BTN_HOME << 8)
                else:   self.btns &= ~(BTN_HOME << 8)
            elif event.code == evdev.ecodes.BTN_THUMBL: # L3
                if val: self.btns |= (BTN_LCLICK << 8)
                else:   self.btns &= ~(BTN_LCLICK << 8)
            elif event.code == evdev.ecodes.BTN_THUMBR: # R3
                if val: self.btns |= (BTN_RCLICK << 8)
                else:   self.btns &= ~(BTN_RCLICK << 8)
                
        elif event.type == evdev.ecodes.EV_ABS:
            # Scale 0-255 -> 0-4095
            if event.code == evdev.ecodes.ABS_X:
                self.lx = int(event.value * 16)
            elif event.code == evdev.ecodes.ABS_Y:
                self.ly = int((255 - event.value) * 16) # Invert Y?
            elif event.code == evdev.ecodes.ABS_RX:
                self.rx = int(event.value * 16)
            elif event.code == evdev.ecodes.ABS_RY:
                self.ry = int((255 - event.value) * 16)
            elif event.code == evdev.ecodes.ABS_HAT0X:
                self.hat_x = event.value
                self.update_hat()
            elif event.code == evdev.ecodes.ABS_HAT0Y:
                self.hat_y = event.value
                self.update_hat()
                
    def update_hat(self):
        # Update Hat Bits in BTNS
        # Hat is bits 0-3 of Byte 2 (btns >> 16)
        # Clear old hat
        self.btns &= ~(0xF << 16)
        
        # Calculate new hat
        h = map_hat(getattr(self, 'hat_x', 0), getattr(self, 'hat_y', 0))
        self.btns |= (h << 16)

if __name__ == "__main__":
    bridge = ProControllerBridge(GADGET_PATH)
    bridge.run()
