# pi-gen-configurator

A tool that lets you configure images for Raspberry Pi. The script will clone [RPi-Distro/pi-gen](https://github.com/RPi-Distro/pi-gen), which is an official tool to create the raspberrypi.org Raspbian images. Then the script will ask for some parameters and make an image.

## Usage

You can run: `./pi-gen-configurator.py --help` to see the up-to-date parameters that can be set.

Parameters can be set either throught command line or they will be asked during the build.

For example we can make an image using the following command (password and passphrase will be asked during the build):

```sh
./pi-gen-configurator.py --hostname "raspberry" --username pi \
  --country_code GB --ssid "WiFi" --authtoken "ngrok_auth_token" \
  --locale "en_GB.UTF-8" --timezone "Europe/London" \
  --keymap gb --layout "English (GB)"
```

## Parameters

The following parameters can be set:

* hostname
* username
* password
* country code for wpa_supplicant.conf
* WiFi SSID
* WiFi passphrase
* ngrok auth token - to start an ngrok tunnel hourly cronjob will be created
* locale
* timezone
* keyboard's keymap and layout

## Outputs

After build finishes, its artifacts can be found at _./artifacts_ directory. _build.log_ containing logs of the build will be placed in root directory.
