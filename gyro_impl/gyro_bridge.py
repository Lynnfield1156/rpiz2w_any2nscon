#!/usr/bin/env python3
import evdev
import struct
import time
import sys
import select
import os

# Constants
GADGET_PATH = "/dev/hidg0"
REPORT_ID = 0x30

# Button Bitmasks (Same as before)
BTN_Y, BTN_B, BTN_A, BTN_X = 0x01, 0x02, 0x04, 0x08
BTN_L, BTN_R, BTN_ZL, BTN_ZR = 0x10, 0x20, 0x40, 0x80
BTN_MINUS, BTN_PLUS = 0x01, 0x02
BTN_LCLICK, BTN_RCLICK = 0x04, 0x08
BTN_HOME, BTN_CAPTURE = 0x10, 0x20
HAT_CENTER = 0x08

# Scaling Factors
# DS4 Accel: Raw ~ -8192 to 8192 for 1G? (Depending on range setting, usually +/- 4G or 8G on evdev)
# Switch Accel: 1G = 4096 (approx)
# We will start with 1:1 or simple identity and tune.
# Most linux ds4 drivers return scaled values or raw.
# Let's assume raw 16-bit signed (-32768 to 32767).

# Switch Calibration Config (Often Switch assumes 1G = 4096)
SWITCH_ACCEL_1G = 4096.0
DS4_ACCEL_1G_EST = 8192.0 # Estimate, need to check `evdev -v` output in reality

def scale_accel(val):
    # Scale DS4 acc to Switch acc
    return int(val * (SWITCH_ACCEL_1G / DS4_ACCEL_1G_EST))

def scale_gyro(val):
    # Gyro scaling is tricky without calibration data.
    # Passing raw might work if ranges are similar.
    # DS4: +/- 2000 dps -> full range?
    return int(val) 

def map_hat(x, y):
    if x == 0 and y == -1: return 0x00
    if x == 1 and y == -1: return 0x01
    if x == 1 and y == 0:  return 0x02
    if x == 1 and y == 1:  return 0x03
    if x == 0 and y == 1:  return 0x04
    if x == -1 and y == 1: return 0x05
    if x == -1 and y == 0: return 0x06
    if x == -1 and y == -1: return 0x07
    return HAT_CENTER

def main():
    print("Waiting for DualShock 4 (Main + Motion)...")
    ds4_main = None
    ds4_motion = None
    
    while ds4_main is None or ds4_motion is None:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            if "Wireless Controller" in dev.name:
                if "Motion Sensors" in dev.name:
                    ds4_motion = dev
                else:
                    ds4_main = dev
        
        if ds4_main and ds4_motion:
            print(f"Found Main: {ds4_main.name}")
            print(f"Found Motion: {ds4_motion.name}")
            break
        print("Searching...")
        time.sleep(1)

    print("Opening gadget output...")
    try:
        gadget_fd = open(GADGET_PATH, "wb")
    except FileNotFoundError:
        print(f"Error: {GADGET_PATH} not found.")
        sys.exit(1)

    # State
    btn_byte1 = 0
    btn_byte2 = 0
    hat_val = HAT_CENTER
    lx, ly, rx, ry = 128, 128, 128, 128
    hat_x, hat_y = 0, 0
    
    # Motion State
    acc_x, acc_y, acc_z = 0, 0, 0
    gyro_x, gyro_y, gyro_z = 0, 0, 0

    print("Bridge started (Gyro Enabled). Press Ctrl+C to stop.")
    
    # Non-blocking reads using select
    fds = {ds4_main.fd: ds4_main, ds4_motion.fd: ds4_motion}

    try:
        while True:
            r, w, x = select.select(fds, [], [])
            
            for fd in r:
                dev = fds[fd]
                for event in dev.read():
                    if dev == ds4_main:
                        # --- Main Controller Handling ---
                        if event.type == evdev.ecodes.EV_KEY:
                            val = event.value
                            if event.code == evdev.ecodes.BTN_SOUTH:
                                if val: btn_byte1 |= BTN_B
                                else:   btn_byte1 &= ~BTN_B
                            elif event.code == evdev.ecodes.BTN_EAST:
                                if val: btn_byte1 |= BTN_A
                                else:   btn_byte1 &= ~BTN_A
                            elif event.code == evdev.ecodes.BTN_WEST:
                                if val: btn_byte1 |= BTN_Y
                                else:   btn_byte1 &= ~BTN_Y
                            elif event.code == evdev.ecodes.BTN_NORTH:
                                if val: btn_byte1 |= BTN_X
                                else:   btn_byte1 &= ~BTN_X
                            elif event.code == evdev.ecodes.BTN_TL:
                                if val: btn_byte1 |= BTN_L
                                else:   btn_byte1 &= ~BTN_L
                            elif event.code == evdev.ecodes.BTN_TR:
                                if val: btn_byte1 |= BTN_R
                                else:   btn_byte1 &= ~BTN_R
                            elif event.code == evdev.ecodes.BTN_TL2:
                                if val: btn_byte1 |= BTN_ZL
                                else:   btn_byte1 &= ~BTN_ZL
                            elif event.code == evdev.ecodes.BTN_TR2:
                                if val: btn_byte1 |= BTN_ZR
                                else:   btn_byte1 &= ~BTN_ZR
                            elif event.code == evdev.ecodes.BTN_SHARE:
                                if val: btn_byte2 |= BTN_MINUS
                                else:   btn_byte2 &= ~BTN_MINUS
                            elif event.code == evdev.ecodes.BTN_OPTIONS:
                                if val: btn_byte2 |= BTN_PLUS
                                else:   btn_byte2 &= ~BTN_PLUS
                            elif event.code == evdev.ecodes.BTN_MODE:
                                if val: btn_byte2 |= BTN_HOME
                                else:   btn_byte2 &= ~BTN_HOME
                            elif event.code == evdev.ecodes.BTN_THUMBL:
                                if val: btn_byte2 |= BTN_LCLICK
                                else:   btn_byte2 &= ~BTN_LCLICK
                            elif event.code == evdev.ecodes.BTN_THUMBR:
                                if val: btn_byte2 |= BTN_RCLICK
                                else:   btn_byte2 &= ~BTN_RCLICK
                        
                        elif event.type == evdev.ecodes.EV_ABS:
                            if event.code == evdev.ecodes.ABS_X: lx = event.value
                            elif event.code == evdev.ecodes.ABS_Y: ly = event.value
                            elif event.code == evdev.ecodes.ABS_RX: rx = event.value
                            elif event.code == evdev.ecodes.ABS_RY: ry = event.value
                            elif event.code == evdev.ecodes.ABS_HAT0X:
                                hat_x = event.value
                                hat_val = map_hat(hat_x, hat_y)
                            elif event.code == evdev.ecodes.ABS_HAT0Y:
                                hat_y = event.value
                                hat_val = map_hat(hat_x, hat_y)

                    elif dev == ds4_motion:
                        # --- Motion Sensor Handling ---
                        # Note: DS4 Accel/Gyro axes mapping varies.
                        # Common: ABS_X/Y/Z = Accel, ABS_RX/RY/RZ = Gyro
                        # Directions also need mapping (DS4 Right Hand System vs Switch)
                        # Switch: Y=Forward?, Z=Up?
                        # DS4: Y=-Forward (or similar)
                        # For now, map directly 1:1 and user can experiment.
                        if event.type == evdev.ecodes.EV_ABS:
                            if event.code == evdev.ecodes.ABS_X: acc_x = scale_accel(event.value)
                            elif event.code == evdev.ecodes.ABS_Y: acc_y = scale_accel(event.value)
                            elif event.code == evdev.ecodes.ABS_Z: acc_z = scale_accel(event.value)
                            elif event.code == evdev.ecodes.ABS_RX: gyro_x = scale_gyro(event.value)
                            elif event.code == evdev.ecodes.ABS_RY: gyro_y = scale_gyro(event.value)
                            elif event.code == evdev.ecodes.ABS_RZ: gyro_z = scale_gyro(event.value)

            # Send Report (periodically or on every event? Switch expects ~60Hz-120Hz)
            # Sending on every event might spam too much if both devices flood events.
            # But simple approach is easiest.
            
            # Stick Scaling (0..255 -> 0..65535)
            slx = min(65535, max(0, int(lx * 257.06)))
            sly = min(65535, max(0, int(ly * 257.06)))
            srx = min(65535, max(0, int(rx * 257.06)))
            sry = min(65535, max(0, int(ry * 257.06)))

            # Pack Values
            # Note regarding IMU alignment:
            # Switch Frame:
            # +X = Right
            # +Y = Up (or Front? need check)
            # +Z = Back (or Up?)
            # DS4 Frame:
            # +X = Right
            # +Y = Down (Back?)
            # +Z = Up
            # We might need to negate/swap some axes.
            # Using basic pack for now.
            
            # Convert to 16-bit signed
            # We must clamp to -32768..32767 for pack 'h'
            def clamp16(v): return max(-32768, min(32767, int(v)))

            ax, ay, az = clamp16(acc_x), clamp16(acc_y), clamp16(acc_z)
            gx, gy, gz = clamp16(gyro_x), clamp16(gyro_y), clamp16(gyro_z)

            # 3 samples of IMU data (Repeating the same sample)
            imu_data = struct.pack('<hhhhhh', ax, ay, az, gx, gy, gz) * 3

            report = struct.pack('<BBBHHHHB', 
                                 REPORT_ID, 
                                 btn_byte1, 
                                 btn_byte2, 
                                 slx, sly, srx, sry, 
                                 hat_val)
            
            # Bytes 12..48 are IMU data (and byte 12 is a timer/tag, let's put 0)
            # Actually Byte 12 should be a timer.
            # Let's verify Report Structure from descriptor or 'joycond'
            # Report 0x30:
            # 0: ID
            # 1: Timer
            # 2: Battery/Connection info (high nibble cmd counter)
            # 3-5: Buttons
            # 6-8: Right Stick
            # 9-11: Left Stick
            # 12: Vibration report (input report from switch contains vib, output report to switch is input state)
            
            # WAIT. The gadget descriptor I used was from mzyy94.
            # It defines a specific format.
            # Byte 0: ID (0x30)
            # Byte 1-11: Standard Input (Buttons/Sticks) AS DEFINED IN THE DESCRIPTOR.
            # Then... in the descriptor:
            # Byte 12-48?: Vendor Defined?
            # The descriptor ends with:
            # ...
            # 0x06, 0x00, 0xFF (Vendor Defined Page)
            # 0x85, 0x21 ...
            # 0x85, 0x30 ...
            #   Joy Stick items...
            #   0x06, 0x00, 0xFF (Usage Page Vendor)
            #   0x85, 0x30 (Report ID 30)
            #   ...
            # The descriptor analysis in blog post was a bit confusing.
            # Let's stick to the struct I used in bridge_controller.py which MATCHED the descriptor analysis:
            # Byte 0: ID
            # Byte 1: Buttons
            # Byte 2: Buttons
            # Byte 3-10: Sticks
            # Byte 11: Hat + Vendor
            # Byte 12...63: Padding
            
            # If we want to send Gyro, we must populate Bytes 12+?
            # Standard Switch Report 0x30 is usually:
            # 0: Timer
            # 1: Battery/Conn
            # 2-4: Buttons
            # 5-7: Left Stick (12-bit packed)
            # 8-10: Right Stick (12-bit packed)
            # 11: Vibrator report
            # 12-48: IMU Data (3 samples)
            
            # BUT Mzyy94's descriptor is NOT the standard Switch descriptor. It is a "Pro Controller Compatible" descriptor but potentially simplified?
            # Or it might be using the 64-byte Vendor Defined section to pass raw data that the Switch *interprets* as Pro Controller data?
            # Actually, mzyy94's blog says "Input... Report ID 0x30... Input Report ID 0x30 only... defined in detail...".
            
            # If we write raw bytes to /dev/hidg0, we are satisfying the descriptor WE WROTE.
            # If our descriptor defines Bytes 0-11 as buttons/sticks, where is Gyro?
            # Is Gyro data even in the descriptor?
            # Switch Pro Controller uses a proprietary protocol inside HID.
            # The descriptor exposes just enough to get the OS to recognize it, but the Switch console speaks a custom protocol on top of it?
            # Or does the Switch use the Descriptor to parse?
            
            # Hypothesis: We need to put the IMU data in the remaining bytes (12-63) even if the descriptor doesn't explicitly name them "Gyro", 
            # OR the descriptor DOES cover them as Vendor Defined payload.
            # Looking at `setup_gadget.sh`:
            # `\\x06\\x00\\xFF` -> Usage Page Vendor
            # `\\x85\\x30` -> Report ID 0x30
            # ... Lots of items ...
            # It ends with `\\x95\\x34\\x81\\x03` -> Report Count 0x34 (52 decimal), Input (Const, Var, Abs) -> Padding/Vendor Data?
            # 52 bytes of vendor data.
            # 1 (ID) + 11 (Buttons/Sticks) + 52 (Vendor) = 64 bytes.
            # Correct!
            # So Bytes 12-63 are the 52 bytes of Vendor Data.
            # This is where the Standard Switch Report format (Timer, Battery, IMU) goes.
            
            # Standard Switch Input Report 0x30 Format (over Bluetooth/UART, but seemingly mapped to HID Vendor Data here):
            # Byte 0: Timer
            # Byte 1: Battery/Connection (e.g. 0x90 = USB, Charging?)
            # Byte 2-4: Buttons (Right, Center, Left)
            # Byte 5-7: Left Stick (12 bit)
            # Byte 8-10: Right Stick (12 bit)
            # Byte 11: Vibrator input?
            # Byte 12-47: IMU Data
            
            # WAIT. My previous implementation (bridge_controller.py) used a CUSTOM mapping:
            # Byte 1: Buttons
            # ...
            # This matched the descriptor's "Button" and "Axis" usages.
            # If the Switch uses the Descriptor to parse, then my previous code works for buttons.
            # But the Switch Console might ignore the descriptor and assume standard ProCon layout if the VID/PID matches.
            # Did the previous code work? (I haven't tested it).
            # The Blog post implies that `mzyy94` made a descriptor that matches what the Switch *expects* or is compatible.
            # If I want to send Gyro, I should likely fill the Vendor Data section (Bytes 12+) with the standard IMU payload.
            
            pad = b'\x00' * (64 - len(report) - 36) # 36 bytes for IMU data
            # Padding needs to be precise. 
            # Current `report` len is 1+1+1+8+1 = 12 bytes.
            # IMU data is 6*2*3 = 36 bytes.
            # Total 48 bytes.
            # Remaining 16 bytes.
            
            # Let's try appending IMU data after the standard buttons/sticks.
            # But wait, standard Pro Packet puts IMU after sticks.
            # Our descriptor defines sticks in bytes 3-10.
            # So Byte 12 starts the Vendor area.
            # Standard Switch packet puts IMU at Byte 13 (offset 13 if 0-indexed including ID?).
            
            # Let's just append the 36-byte IMU data strictly after the first 12 bytes.
            # And fill the rest with zeros.
            
            full_report = report + imu_data + b'\x00' * (64 - 12 - 36)
            
            gadget_fd.write(full_report)
            gadget_fd.flush()

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        gadget_fd.close()

if __name__ == "__main__":
    main()
