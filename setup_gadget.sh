#!/bin/bash

# Stop on errors
set -e

# Pro Controller Gadget Setup
CONFIGFS_HOME=/sys/kernel/config/usb_gadget
GADGET_NAME=procon

cd $CONFIGFS_HOME
if [ -d "$GADGET_NAME" ]; then
    echo "Gadget $GADGET_NAME already exists. Removing..."
    # Disable gadget
    echo "" > $GADGET_NAME/UDC || true
    # Remove configs
    rm $GADGET_NAME/configs/c.1/hid.usb0 || true
    rmdir $GADGET_NAME/configs/c.1/strings/0x409 || true
    rmdir $GADGET_NAME/configs/c.1 || true
    # Remove functions
    rmdir $GADGET_NAME/functions/hid.usb0 || true
    # Remove strings
    rmdir $GADGET_NAME/strings/0x409 || true
    # Remove gadget
    rmdir $GADGET_NAME || true
fi

echo "Creating gadget $GADGET_NAME..."
mkdir $GADGET_NAME
cd $GADGET_NAME

# ID setup (Pro Controller)
echo 0x057e > idVendor
echo 0x2009 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB
echo 0x00 > bDeviceClass
echo 0x00 > bDeviceSubClass
echo 0x00 > bDeviceProtocol

# Strings
mkdir -p strings/0x409
echo "000000000001" > strings/0x409/serialnumber
echo "HORI CO.,LTD." > strings/0x409/manufacturer
echo "POKKEN CONTROLLER" > strings/0x409/product

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "POKKEN CONTROLLER" > configs/c.1/strings/0x409/configuration
echo 500 > configs/c.1/MaxPower
echo 0x80 > configs/c.1/bmAttributes

# HID Function
mkdir -p functions/hid.usb0
echo 0 > functions/hid.usb0/protocol
echo 0 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
# Report Descriptor (Pokken Controller - 8 bytes)
# Usage Page (Desktop), Usage (Joystick)
# Collection (Application)
#   Report ID (none)
#   Usage Page (Button), Usage Min (1), Usage Max (14)
#   Logical Min (0), Logical Max (1)
#   Report Size (1), Report Count (14)
#   Input (Data, Var, Abs)
#   Report Size (1), Report Count (2) -> Padding
#   Input (Cnst, Var, Abs)
#   Usage Page (Desktop), Usage (Hat Switch)
#   Logical Min (0), Logical Max (7), Physical Min (0), Physical Max (315)
#   Report Size (4), Report Count (1), Unit (Deg)
#   Input (Data, Var, Abs, Null)
#   Usage (X), Usage (Y), Usage (Z), Usage (Rz) -> LX, LY, RX, RY
#   Logical Min (0), Logical Max (255)
#   Report Size (8), Report Count (4)
#   Input (Data, Var, Abs)
#   Report Size (8), Report Count (1) -> Vendor/Padding
#   Input (Cnst, Var, Abs)
# End Collection
python3 -c 'import sys; sys.stdout.buffer.write(b"\x05\x01\x09\x04\xa1\x01\x05\x09\x19\x01\x29\x0e\x15\x00\x25\x01\x75\x01\x95\x0e\x81\x02\x75\x01\x95\x02\x81\x01\x05\x01\x09\x39\x15\x00\x25\x07\x35\x00\x46\x3b\x01\x65\x14\x75\x04\x95\x01\x81\x42\x05\x01\x09\x30\x09\x31\x09\x32\x09\x35\x15\x00\x26\xff\x00\x75\x08\x95\x04\x81\x02\x75\x08\x95\x01\x81\x01\xc0")' > functions/hid.usb0/report_desc

# Link Function
ln -s functions/hid.usb0 configs/c.1/

# Enable Gadget
ls /sys/class/udc > UDC

echo "Gadget setup complete. HID device should be at /dev/hidg0"
