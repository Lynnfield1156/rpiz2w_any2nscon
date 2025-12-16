#!/usr/bin/env python3
import evdev
import struct
import time
import sys
import os

# Constants
GADGET_PATH = "/dev/hidg0"
REPORT_ID = 0x30

# Switch Pro Controller Button Bitmasks
# Byte 1
BTN_Y       = 0x01
BTN_B       = 0x02
BTN_A       = 0x04
BTN_X       = 0x08
BTN_L       = 0x10
BTN_R       = 0x20
BTN_ZL      = 0x40
BTN_ZR      = 0x80

# Byte 2
BTN_MINUS   = 0x01
BTN_PLUS    = 0x02
BTN_LCLICK  = 0x04
BTN_RCLICK  = 0x08
BTN_HOME    = 0x10
BTN_CAPTURE = 0x20
# Bits 6,7 unused

# Byte 11 (Hat + Vendor)
# Hat is lower 4 bits (0-7, 8=Center)
HAT_TOP          = 0x00
HAT_TOP_RIGHT    = 0x01
HAT_RIGHT        = 0x02
HAT_BOTTOM_RIGHT = 0x03
HAT_BOTTOM       = 0x04
HAT_BOTTOM_LEFT  = 0x05
HAT_LEFT         = 0x06
HAT_TOP_LEFT     = 0x07
HAT_CENTER       = 0x08

# Vendor specific (upper 4 bits of Byte 11) - usually 0

# Safe Button Access for older evdev/kernels
BTN_SHARE_CODE = getattr(evdev.ecodes, 'BTN_SHARE', getattr(evdev.ecodes, 'BTN_SELECT', 314))
BTN_OPTIONS_CODE = getattr(evdev.ecodes, 'BTN_OPTIONS', getattr(evdev.ecodes, 'BTN_START', 315))
BTN_MODE_CODE = getattr(evdev.ecodes, 'BTN_MODE', 316)


def scale_axis(value):
    # DS4: 0..255 -> Switch: 0..65535
    # DS4 Center is 128 (approx), Switch Center is 32768
    # Simple linear scaling: value * 257 (approx)
    return min(65535, max(0, int(value * 257.06)))

def map_hat(x, y):
    # DS4 ABS_HAT0X: -1 (Left), 0, 1 (Right)
    # DS4 ABS_HAT0Y: -1 (Up), 0, 1 (Down)
    if x == 0 and y == -1: return HAT_TOP
    if x == 1 and y == -1: return HAT_TOP_RIGHT
    if x == 1 and y == 0:  return HAT_RIGHT
    if x == 1 and y == 1:  return HAT_BOTTOM_RIGHT
    if x == 0 and y == 1:  return HAT_BOTTOM
    if x == -1 and y == 1: return HAT_BOTTOM_LEFT
    if x == -1 and y == 0: return HAT_LEFT
    if x == -1 and y == -1: return HAT_TOP_LEFT
    return HAT_CENTER

def main():
    print("Opening gadget output...")
    try:
        gadget_fd = open(GADGET_PATH, "wb")
    except FileNotFoundError:
        print(f"Error: {GADGET_PATH} not found. Did you run setup_gadget.sh?")
        sys.exit(1)

    try:
        while True:
            print("Waiting for DualShock 4...")
            ds4_device = None
            
            # Search Loop
            while ds4_device is None:
                devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
                for dev in devices:
                    if "Sony Interactive Entertainment Wireless Controller" in dev.name or "Wireless Controller" in dev.name:
                        # Skip Touchpad and Motion Sensors
                        if "Touchpad" in dev.name or "Motion Sensors" in dev.name:
                            continue
                        ds4_device = dev
                        print(f"Found DS4: {dev.name} ({dev.phys})")
                        break
                if ds4_device is None:
                    time.sleep(1)

            # State
            btn_byte1 = 0
            btn_byte2 = 0
            hat_value = HAT_CENTER
            
            # Axes (Default Center)
            lx = 128
            ly = 128
            rx = 128
            ry = 128
            
            hat_x = 0
            hat_y = 0

            print("Bridge started. Press Ctrl+C to stop.")

            try:
                for event in ds4_device.read_loop():
                    # Update State
                    if event.type == evdev.ecodes.EV_KEY:
                        val = event.value # 1=Press, 0=Release
                        print(f"DEBUG: Button Code {event.code} {'Pressed' if val else 'Released'}")
                        
                        # DS4 Mapping
                        # A/B/X/Y (DS4: Cross/Circle/Square/Triangle) -> Switch: B/A/Y/X
                        if event.code == evdev.ecodes.BTN_SOUTH: # Cross
                            if val: btn_byte1 |= BTN_B
                            else:   btn_byte1 &= ~BTN_B
                        elif event.code == evdev.ecodes.BTN_EAST: # Circle
                            if val: btn_byte1 |= BTN_A
                            else:   btn_byte1 &= ~BTN_A
                        elif event.code == evdev.ecodes.BTN_WEST: # Square
                            if val: btn_byte1 |= BTN_Y
                            else:   btn_byte1 &= ~BTN_Y
                        elif event.code == evdev.ecodes.BTN_NORTH: # Triangle
                            if val: btn_byte1 |= BTN_X
                            else:   btn_byte1 &= ~BTN_X
                        
                        # Triggers / Shoulders
                        elif event.code == evdev.ecodes.BTN_TL: # L1
                            if val: btn_byte1 |= BTN_L
                            else:   btn_byte1 &= ~BTN_L
                        elif event.code == evdev.ecodes.BTN_TR: # R1
                            if val: btn_byte1 |= BTN_R
                            else:   btn_byte1 &= ~BTN_R
                        elif event.code == evdev.ecodes.BTN_TL2: # L2
                            if val: btn_byte1 |= BTN_ZL
                            else:   btn_byte1 &= ~BTN_ZL
                        elif event.code == evdev.ecodes.BTN_TR2: # R2
                            if val: btn_byte1 |= BTN_ZR
                            else:   btn_byte1 &= ~BTN_ZR
                        
                        # Special Buttons
                        elif event.code == BTN_SHARE_CODE: # Share
                            if val: btn_byte2 |= BTN_MINUS
                            else:   btn_byte2 &= ~BTN_MINUS
                        elif event.code == BTN_OPTIONS_CODE: # Options
                            if val: btn_byte2 |= BTN_PLUS
                            else:   btn_byte2 &= ~BTN_PLUS
                        elif event.code == BTN_MODE_CODE: # PS
                            if val: btn_byte2 |= BTN_HOME
                            else:   btn_byte2 &= ~BTN_HOME
                        elif event.code == evdev.ecodes.BTN_THUMBL: # L3
                            if val: btn_byte2 |= BTN_LCLICK
                            else:   btn_byte2 &= ~BTN_LCLICK
                        elif event.code == evdev.ecodes.BTN_THUMBR: # R3
                            if val: btn_byte2 |= BTN_RCLICK
                            else:   btn_byte2 &= ~BTN_RCLICK
                        # Touchpad Click -> Capture
                        # Note: evdev code for touchpad click varies, often BTN_TOUCH or similar.
                        # Assuming generic mapping or avoiding if unsure. 
                        # Let's map L2 trigger (if it was a button) or something else?
                        # Actually DS4 has a dedicated touchpad click button, often code 317 (BTN_THUMB2?) or BTN_LEFT/RIGHT on mouse.
                        # Let's assume we skip capture for now or map it to something unused if possible.
                        # Better yet, map it so user can use it.
                        
                    elif event.type == evdev.ecodes.EV_ABS:
                        print(f"DEBUG: Abs Code {event.code} Value {event.value}")
                        if event.code == evdev.ecodes.ABS_X:
                            lx = event.value
                        elif event.code == evdev.ecodes.ABS_Y:
                            ly = event.value
                        elif event.code == evdev.ecodes.ABS_RX:
                            rx = event.value
                        elif event.code == evdev.ecodes.ABS_RY:
                            ry = event.value
                        elif event.code == evdev.ecodes.ABS_HAT0X:
                            hat_x = event.value
                            hat_value = map_hat(hat_x, hat_y)
                        elif event.code == evdev.ecodes.ABS_HAT0Y:
                            hat_y = event.value
                            hat_value = map_hat(hat_x, hat_y)

                    # Construct Report
                    # 64 bytes total
                    # Byte 0: ID
                    # Byte 1: Buttons 1
                    # Byte 2: Buttons 2
                    # Byte 3-4: LX LE
                    # Byte 5-6: LY LE
                    # Byte 7-8: RX LE
                    # Byte 9-10: RY LE
                    # Byte 11: Hat
                    # Rest: 0
                    
                    # Switch Stick logic might need calibration info, but this rawHID report structure 
                    # usually expects:
                    # Hori Pad Mapping (Standard HID)
                    # Descriptor defines 16 buttons.
                    # Byte 0: Bits 0-7 -> Y, B, A, X, L, R, ZL, ZR
                    # Byte 1: Bits 8-15 -> Minus, Plus, L3, R3, Home, Capture, ?, ?
                    
                    # Re-map DS4 buttons to Hori Bitmask
                    # Note: DS4 Logic in loop stays the same, we just need to pack them differently.
                    # Current variables: btn_byte1, btn_byte2 are used.
                    # Let's adjust strict bit assignments if needed, or just repack.
                    
                    # Our current btn_byte1: Y(1), B(2), A(4), X(8), L(10), R(20), ZL(40), ZR(80)
                    # This MATCHES standard button order for bits 0-7!
                    # Our current btn_byte2: Minus(1), Plus(2), LClick(4), RClick(8), Home(10), Capture(20)
                    # This also MATCHES bits 8-13!
                    
                    # Sticks
                    # Descriptor says 8-bit (0-255).
                    # DS4 raw is 0-255.
                    # So 1:1 mapping! No scaling needed.
                    
                    h_lx = lx
                    h_ly = ly
                    h_rx = rx
                    h_ry = ry
                    
                    # Report Construction (8 bytes)
                    # Byte 0: Buttons Low
                    # Byte 1: Buttons High
                    # Byte 2: Hat
                    # Byte 3: LX
                    # Byte 4: LY
                    # Byte 5: RX
                    # Byte 6: RY
                    # Byte 7: 0
                    
                    # Report ID is NOT used in this simple descriptor.
                    
                    report = struct.pack('<BBBBBBBB', 
                                         btn_byte1, 
                                         btn_byte2, 
                                         hat_value, 
                                         h_lx, h_ly, h_rx, h_ry, 
                                         0)
                    
                    # Debug Output
                    print(f"DEBUG: SEND USB -> B1:{btn_byte1:02X} B2:{btn_byte2:02X} Hat:{hat_value} LX:{h_lx} LY:{h_ly} RX:{h_rx} RY:{h_ry}")
        
                    try:
                        gadget_fd.write(report)
                        gadget_fd.flush()
                    except OSError as e:
                        # Errno 108: Cannot send after transport endpoint shutdown (USB disconnected)
                        # Errno 32: Broken pipe
                        if e.errno in [108, 32]:
                            # Optional: Print warning only once or periodically
                            # print("Waiting for USB host connection...") 
                            pass
                        else:
                            raise

            except OSError as e:
                # Errno 19: No such device (Controller disconnected)
                if e.errno == 19:
                    print("Controller disconnected. Searching...")
                    continue
                else:
                    raise

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        gadget_fd.close()

if __name__ == "__main__":
    main()
