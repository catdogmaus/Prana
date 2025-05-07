## About This Integration
[![GitHub](https://img.shields.io/github/license/catdogmaus/Prana?color=green)](https://github.com/catdogmaus/Prana/blob/main/LICENSE)  
**Prana Recuperators** allows Home Assistant to interface thru Bluetooth with [Prana Recuperators].

### Features

- Does recognize and configure Prana device using device mac address. For mac address look at `Readme`
- Configuration via UI (Config Flow)

### Installation

1. Add this repository as a custom repository in HACS.
2. Install the integration from HACS → Integrations.
3. Restart Home Assistant.
4. Configure via Settings → Devices & Services.

### Configuration

This integration uses the config flow UI. No YAML required.
In Devices clik `add integration`, search Prana and follow config flow.

### Troubleshooting

If the integration does not show up:
- Check logs for errors 
- Ensure the integration is installed in `custom_components/prana`
- Make sure you restarted HA after integration installation thru HACS

---

For more details, visit the [GitHub repository](https://github.com/catdogmaus/Prana).

