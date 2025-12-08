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

# ID setup (Nintendo Switch Pro Controller)
echo 0x057e > idVendor
echo 0x2009 > idProduct
echo 0x0200 > bcdDevice
echo 0x0200 > bcdUSB
echo 0x00 > bDeviceClass
echo 0x00 > bDeviceSubClass
echo 0x00 > bDeviceProtocol

# Strings
mkdir -p strings/0x409
echo "000000000001" > strings/0x409/serialnumber
echo "Nintendo Co., Ltd." > strings/0x409/manufacturer
echo "Pro Controller" > strings/0x409/product

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "Nintendo Switch Pro Controller" > configs/c.1/strings/0x409/configuration
echo 500 > configs/c.1/MaxPower
echo 0xa0 > configs/c.1/bmAttributes

# HID Function
mkdir -p functions/hid.usb0
echo 0 > functions/hid.usb0/protocol
echo 0 > functions/hid.usb0/subclass
echo 64 > functions/hid.usb0/report_length
# Report Descriptor (from mzyy94 analysis)
echo -ne \\x05\\x01\\x15\\x00\\x09\\x04\\xA1\\x01\\x85\\x30\\x05\\x01\\x05\\x09\\x19\\x01\\x29\\x0A\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x0A\\x55\\x00\\x65\\x00\\x81\\x02\\x05\\x09\\x19\\x0B\\x29\\x0E\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x04\\x81\\x02\\x75\\x01\\x95\\x02\\x81\\x03\\x0B\\x01\\x00\\x01\\x00\\xA1\\x00\\x0B\\x30\\x00\\x01\\x00\\x0B\\x31\\x00\\x01\\x00\\x0B\\x32\\x00\\x01\\x00\\x0B\\x35\\x00\\x01\\x00\\x15\\x00\\x27\\xFF\\xFF\\x00\\x00\\x75\\x10\\x95\\x04\\x81\\x02\\xC0\\x0B\\x39\\x00\\x01\\x00\\x15\\x00\\x25\\x07\\x35\\x00\\x46\\x3B\\x01\\x65\\x14\\x75\\x04\\x95\\x01\\x81\\x02\\x05\\x09\\x19\\x0F\\x29\\x12\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x04\\x81\\x02\\x75\\x08\\x95\\x34\\x81\\x03\\x06\\x00\\xFF\\x85\\x21\\x09\\x01\\x75\\x08\\x95\\x3F\\x81\\x03\\x85\\x81\\x09\\x02\\x75\\x08\\x95\\x3F\\x81\\x03\\x85\\x01\\x09\\x03\\x75\\x08\\x95\\x3F\\x91\\x83\\x85\\x10\\x09\\x04\\x75\\x08\\x95\\x3F\\x91\\x83\\x85\\x80\\x09\\x05\\x75\\x08\\x95\\x3F\\x91\\x83\\x85\\x82\\x09\\x06\\x75\\x08\\x95\\x3F\\x91\\x83\\xC0 > functions/hid.usb0/report_desc

# Link Function
ln -s functions/hid.usb0 configs/c.1/

# Enable Gadget
ls /sys/class/udc > UDC

echo "Gadget setup complete. HID device should be at /dev/hidg0"
