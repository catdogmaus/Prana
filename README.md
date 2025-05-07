# Prana
Allows Home Assistant to interface thru Bluetooth with Prana Recuperators

**This integration is not yet ready for use!**  
However it should install Prana device thru config flow withot any actual device data yet.
If you are able, you are free to fork it and make it to work yourself.

## Installation via HACS

1. Go to HACS
2. Click the `⋮` button in corner
3. Add this repository as a **custom repository** (`https://github.com/catdogmaus/Prana`)
4. Select "Integration"
5. Restart Home Assistant

## How to find device mac address

This integration should be able to discover Prana devices and offer to add them as new devices, however because how HA Bluetooth works, this turned out to be very unreliable. You can still add new device using its mac address.
For you device mac addres go to `Integrations` click `Bluetooth` and then below `Integration entries` `configure`. There, under `advertisement monitor` you should see all BT devices and their addresses in HA Bluetooth range. When you cant see it there, you need to move you HA device close to Prana device or use Bluetooth proxy.

## How to add new Prana device

If you HA does not discover your device automatically, in `Devices and Services` clik `Add Integration`, search `Prana` and follow configuration flow.

## Problems with adding Prana device

When you are unable to add new device even with manual setup make sure that Prana is not connected to any other device (e.g. native Prana app). Also make sure your HA Bluetooth `Connection slot allocations monitor` is not full!
