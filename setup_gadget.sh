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
    echo "" > $GADGET_NAME/UDC
    # Remove configs
    rm $GADGET_NAME/configs/c.1/hid.usb0
    rmdir $GADGET_NAME/configs/c.1/strings/0x409
    rmdir $GADGET_NAME/configs/c.1
    # Remove functions
    rmdir $GADGET_NAME/functions/hid.usb0
    # Remove strings
    rmdir $GADGET_NAME/strings/0x409
    # Remove gadget
    rmdir $GADGET_NAME
fi

echo "Creating gadget $GADGET_NAME..."
mkdir $GADGET_NAME
cd $GADGET_NAME

# ID setup (HORIPAD S -> Pokken)
echo 0x0f0d > idVendor
echo 0x0092 > idProduct
echo 0x0200 > bcdDevice
echo 0x0200 > bcdUSB
echo 0x00 > bDeviceClass
echo 0x00 > bDeviceSubClass
echo 0x00 > bDeviceProtocol

# Strings
mkdir -p strings/0x409
echo "000000000001" > strings/0x409/serialnumber
echo "HORI CO.,LTD." > strings/0x409/manufacturer
echo "HORIPAD S" > strings/0x409/product

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "HORIPAD S" > configs/c.1/strings/0x409/configuration
echo 500 > configs/c.1/MaxPower
echo 0xa0 > configs/c.1/bmAttributes

# HID Function
mkdir -p functions/hid.usb0
echo 0 > functions/hid.usb0/protocol
echo 0 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
# Report Descriptor (Standard Gamepad - 8 bytes)
# Usage Page (Generic Desktop), Usage (Gamepad)
# Bytes 0-1: Buttons (16 bits)
# Byte 2: Hat (0-7, 8=Center)
# Byte 3: LX
# Byte 4: LY
# Byte 5: RX
# Byte 6: RY
# Byte 7: Venom/Extra
# Report Descriptor (Match NintendoSwitchControlLibrary)
# Bytes 0-1: Buttons
# Byte 2: Hat
# Bytes 3-6: Sticks
# Byte 7: Vendor
# + Output Report (8 bytes)
echo -ne \\x05\\x01\\x09\\x05\\xa1\\x01\\x15\\x00\\x25\\x01\\x35\\x00\\x45\\x01\\x75\\x01\\x95\\x10\\x05\\x09\\x19\\x01\\x29\\x10\\x81\\x02\\x05\\x01\\x25\\x07\\x46\\x3b\\x01\\x75\\x04\\x95\\x01\\x65\\x14\\x09\\x39\\x81\\x42\\x65\\x00\\x95\\x01\\x81\\x01\\x26\\xff\\x00\\x46\\xff\\x00\\x09\\x30\\x09\\x31\\x09\\x32\\x09\\x35\\x75\\x08\\x95\\x04\\x81\\x02\\x06\\x00\\xff\\x09\\x20\\x95\\x01\\x81\\x02\\x0a\\x21\\x26\\x95\\x08\\x91\\x02\\xc0 > functions/hid.usb0/report_desc

# Link Function
ln -s functions/hid.usb0 configs/c.1/

# Enable Gadget
ls /sys/class/udc > UDC

echo "Gadget setup complete. HID device should be at /dev/hidg0"
