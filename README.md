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

The following parameters can be set either using command line or during the build:

* `-o HOSTNAME` or `--hostname HOSTNAME` to set hostname
* `-u USERNAME` or `--username USERNAME` to set username
* `-p PASSWORD` or `--password PASSWORD` to set user password
* `-c COUNTRY_CODE` or `--country-code COUNTRY_CODE` WiFi Country Code (can be found at https://en.wikipedia.org/wiki/ISO_3166-1)
* `-s SSID` or `--ssid SSID` to set WiFi SSID
* `-w PASSPHRASE` or `--passphrase PASSPHRASE` WiFi Passphrase
* `--skip-ngrok` skip ngrok
* `-a AUTHTOKEN` or `--authtoken AUTHTOKEN` to set ngrok auth token
* `-l LOCALE` or `--locale LOCALE` to set locale (e.g. en_US.UTF-8)
* `-t TIMEZONE` or `--timezone TIMEZONE` to set timezone (e.g. America/New_York, can be found at https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
* `-k KEYMAP` or `--keymap KEYMAP` to set keyboard keymap (gb, us, etc.)
* `-y LAYOUT` or `--layout LAYOUT` to set keyboard layout (English (US), English (UK), etc.)

## Outputs

After build finishes, its artifacts can be found at _./artifacts_ directory. _build.log_ containing logs of the build will be placed in root directory.
