# pstnxsip

This project aims to implement an IP PBX with an FXO interface to PSTN analog phone line using a USB modem. Those provide to call PSTN numbers from and to answer PSTN calls from VoIP client running on mobile phone. All codes are tested. Unit is connected home PSTN phone line. It is functioning as a PSTN-VoIP Gateway.

# Functions
- PSTN-VoIP Gateway:
User can use PSTN analog phone line from a mobile phone. Requires two SIP accounts. Mobile phone SIP client application must support 'push'. Only the SIP account got for mobile phone can call the unit and make outbound calls to PSTN.
- IP FXO:
IP PBX can be configured to use this client's internal number as a trunk. (See Asterisk config files)
- IVR or answering/recording machine:
Unit can record all (inbound & outbound) calls to the folder where the code running. To add other functionality, coding required.

# Known Issues
First, after Apple and Google's mobile device power consumption policy change, there is still a few free VoIP client supports running in the background/lock screen. Your VoIP client and VoIP provider must support push notification.

Second, USB Modem does not support echo cancellation in 'Voice Mode'. Tried to implement a simple method to suppress echo (Disabled in actual config, because there is no disturbing echo). It can be changed with a better algorithm if you have more resources on your board. 

Made many changes on codes found on github to make resource optimization. Still there are some points. For example, there is no double audio buffer. This sometimes causes modem transmit buffer underruns and rarely produces some noise.

# Thanks to:
- https://github.com/ophub for amlogic-s9xxx-armbian/releases
- https://gist.github.com/kolosek for asterisk.sh
- https://github.com/tayler6000 for pyVoIP
- https://github.com/pradeesi for play_audio_over_phone_line and record_audio_from_phone_line
- https://unix.stackexchange.com/questions/233646/run-a-python-script-in-the-background-on-boot for running as a service.
- https://www.voip-info.org/

# Hardware and Software Components
### H96 Mini, Android TV box: S905W CPU, 2 GB RAM, 16 GB eMMC. Armbian_23.02.0/bullseye_5.15.88/server installed.
Any board with enough resource (CPU speed, run time memory, program memory and USB port) is suitable. With this hardware and software configuration, during an audio session, CPU handles one loop in 2-3 ms at 1 GHz.
### Conexant RD02-D400 USB Modem: CX93010 Chipset.
Modem must be a 'Voice Modem', if modem does not support 'Voice Mode' (+FCLASS=8) can not be used.
### Asterisk 16 LTS IP PBX:
After default installation, delete all config files and copy only four from project 'asterisk' folder. If you already have a running IP PBX, you can pass installation steps. If you experienced with Asterisk you can add/remove features. Do not use Playback() routine in dial plan if you want to use hunt group with this project.
### Python3:
python3-pip, pyserial modules.
### pstnxsip files:
common.py, ip_phone.py, line.py, pstnxsip.py, dial.wav, ringback.wav


# Armbian installation on H96 Mini (Search internet for more resources)
### !!! Caution, steps below may harm your Android TV and can cause reboot loops or other severe issues !!!
If you don't have an original ROM image and you don't know how to use 'Amlogic USB Burning Tool 2.2.0', do not forward!

Connect to a TV or monitor your H96 Mini then open and find its IP address.

From https://github.com/ophub/amlogic-s9xxx-armbian/releases download Armbian_23.02.0_amlogic_s905w_bullseye_5.15.XX_server_YYYY.MM.DD.img.

Use proper image tool to prepare SD card or USB memory: in Windows systems you can use Rufus, in Linux systems you can use 'sudo dd if=XXX.img of=/dev/sdX' (X for related disk)

Connect your SD card or USB memory (8 GB is enough without recording) to H96 Mini then find 'Update & Backup' utility in menu and try if it can find the bootloader. If it couldn't try steps below:

Install android 'adb' utility from Google (Android\Sdk\platform-tools) then run

'adb connect H96_Mini_IP_address'

'adb shell' (opens a remote shell)

'reboot update' (reboots to Armbian)

After reboot, Armbian first config will runs and asks for some parameters. Set a strong root password and add another user if you prefer.

Add second user (if you created when Armbian installation) to dialout group with 'sudo adduser second_user dialout' to give dial-out permission. You may give additional permissions (like sudoers) when require. 

Run 'sudo armbian-config' then change; CPU speed to '500-1200', governor to 'performance', disable 'IPV6 support'.

If you plan to use Wi-Fi: Select 'Wi-Fi Config' and connect to a Wi-Fi network, exit from armbian-config and reboot to check if Wi-Fi is still working. (Wi-Fi rarely works with Armbian on this android TV models)

Set static IP address, Hostname, Change Date/Time, Locale and Keyboard settings. If keyboard setting does not work properly run 'sudo nano /etc/default/keyboard' and edit lines (for TR, Turkish Q)

	XKBMODEL="pc105"
	XKBLAYOUT="tr"
	XKBVARIANT="intl"

To check if all disk size is utilizing use 'df' and 'lsblk -f' commands. If you need to extend partition size use: https://access.redhat.com/articles/1190213

Check if all configurations are working. If you planned to install Asterisk you should add a secondary IP.

Find connection 'NAME' on list with 'sudo nmcli connection show' and add with 'sudo nmcli con mod NAMEOFCONNECTION +ipv4.addresses "192.168.1.111/24"'

Then reboot with 'sudo reboot' (or 'shutdown -r now'). After reboot, check configuration with 'sudo nmcli device show' and ping to IP. 

Update system with 'sudo apt update && sudo apt -y upgrade' then reboot.

# Asterisk 16 Installation

Used install script from https://gist.github.com/kolosek/d014b4a4c3b1917e61c40f70067796ec

After installation delete all folder contents of /etc/asterisk/ and copy 4 config files from project Asterisk folder. Install and configure a VoIP client to your mobile phone or PC to test Asterisk is working as expected.

# Python 3 Installation

sudo apt install python3

sudo apt install python3-pip

sudo pip install pyserial

# Find USB Modem Port Name

Connect USB modem and see its device name with 'ls /dev'. You should see /dev/ttyACM0 or similar.

# pstnxsip Files Installation

Create folder with 'sudo mkdir /home/pstnxsip' and copy project files (pstnxsip.py, line.py, ip_phone.py, common.py, ringback.wav, dial.wav) to this folder. Edit common.py and change all required parameters (modem port, ip addreses, VoIP accounts etc.) according to your system configuration.

Go to this folder 'cd /home/pstnxsip' and run with 'sudo python3 pstnxsip.py'. Make tests then

### Make the project runs as a service.

Used https://unix.stackexchange.com/questions/233646/run-a-python-script-in-the-background-on-boot.

Step 1: Run 'sudo nano /lib/systemd/system/pstnxsip.service'.

Step 2: Add lines below and save file.
```
[Unit]
Description=PSTNxSIP Python script

[Service]
WorkingDirectory=/home/pstnxsip
ExecStart=/usr/bin/python3 /home/pstnxsip/pstnxsip.py
Restart=always
# Restart service after 10 seconds if the service crashes.
RestartSec=10
KillSignal=SIGINT
SyslogIdentifier=pstnxsip

[Install]
WantedBy=multi-user.target
```

Step3: Enable and start the service with 'sudo systemctl enable pstnxsip.service' and 'sudo systemctl start pstnxsip.service'.

To stop and disable the service: 'sudo systemctl stop pstnxsip.service' and 'sudo systemctl disable pstnxsip.service'.

To show service status: 'sudo systemctl status pstnxsip.service'.

To show log (if enabled DEBUGPRINT = True, you would see debug lines in the log): 'sudo journalctl -fu pstnxsip.service'.
