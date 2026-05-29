[![GitHub](https://img.shields.io/github/license/catdogmaus/Prana?color=green)](https://github.com/catdogmaus/Prana/blob/main/LICENSE)  [![](https://img.shields.io/github/release/catdogmaus/Prana/all.svg)](https://github.com/catdogmaus/Prana/releases) 
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)<br/>
<span class="badge-buymeacoffee">
<a href="https://ko-fi.com/catdog58928" title="Support this project using Ko-Fi"><img src="https://img.shields.io/badge/Buy_me_coffee_or_biscuits-support-yellow.svg?style=for-the-badge&logo=kofi" alt="Buy Me A Coffee  button" /></a>
</span><br/> 

# Prana Bluetooth recuperators
This is unofficial app for older Prana buetooth devices that allows Home Assistant to interface thru Bluetooth with Prana 150/200 Recuperators.

The idea for creating integration comes from the work of https://github.com/voed/esphome_prana_ble but nothing that had been done by others so far worked quite well with my device.

## Installation via HACS

1. Go to HACS
2. Click the `⋮` button in corner
3. Add this repository as a **custom repository** (`https://github.com/catdogmaus/Prana`)
4. Select "Integration"
5. Restart Home Assistant

## Setup

This integration should be able to discover Prana devices and offer to add them as new devices, just follow the config flow. However when discovery fails for some reason, you can still add new device using its mac address.
For you device mac addres go to `Settings` click `Bluetooth` and then below `Adapters` or `Map`. you should see all BT devices and their addresses in HA Bluetooth range. When you cant see it there, you need to move you HA device close to Prana device or use Bluetooth proxy.

## Different models

This integration has been tested with the `Premium Plus` model and I don't have the options to do it with the `Premium` and `Standard` models, so I literally had to guess what sensors and features are available in these other versions exactly. If you find that a feature is missing or something shouldn't be there, you can open an issue and hopefully I can fix it when I have time. For that I need exact model and a description of what you think is missing or excessive in the settings.
If, despite everything, you still can't connect your device at all, it's probably an incompatible version (newer or older). In that case, your out of luck. I have no way to test them and get to work with this integration.

## Other noteworthy things

The Prana device does not reliably report the position of the screen, so the integration essentially has to guess what position it actually is. This works pretty well, but if someone uses the remote control in the meantime, there is an understandable gap in the integration's knowledge. If the screen is out of sync, the easiest way to get it back is to briefly change the operating mode, Auto or Manual. This helps the integration heal its knowledge.

Winter setting is untested. It is simply not possible to do this in summer.

The filter warning is a simple counter. Prana recommends performing a full maintenance at least once a year, but you can change this interval to your exact preference in the settings.

The Prana device has a very annoying feature of moving the device's display every time the mode is changed to the default fan speed. The integration has the ability to override this. Your screen will remain in the same position as before. However, if you are not happy with this for any reason, you can disable this behavior in the settings.

Depending of you system, connection to device after HA restart could take several minutes so dont panic. ;)

## Problems with adding Prana device

When you are unable to add new device even with manual setup make sure that Prana is not connected to any other device (e.g. native Prana app). Also make sure your HA Bluetooth `Connections` slots is not full!
