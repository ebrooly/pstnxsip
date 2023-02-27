# pstnxsip

This project aims to implement an IP PBX with an FXO interface to PSTN analog line using a USB modem. Those provide to call PSTN numbers from and to answer PSTN calls from VoIP client running on mobile phone.

# Known Issues
First, there is a few free VoIP client supports running in the background/lock screen after Apple and Google's mobile device power consumption policy change. Your VoIP client and VoIP provider must support push notification.    

Second, USB Modem does not support echo cancellation in 'Voice Mode'. Tried to implement a simple method to suppress echo (Disabled in actual config). It can be changed with a better algorithm if you have more resources on your board.

Made many changes on codes found on github to make resource optimization. Still there are some points. For example, there is no audio buffer. This causes modem transmit buffer underruns sometimes and produces some noise.

# Thanks to:
- https://github.com/ophub for amlogic-s9xxx-armbian/releases
- https://gist.github.com/kolosek for asterisk.sh
- https://github.com/tayler6000 for pyVoIP
- https://github.com/pradeesi for play_audio_over_phone_line and record_audio_from_phone_line
- https://www.voip-info.org/

# Hardware and Software Components
- H96 Mini, Android TV box: S905W CPU, 2 GB RAM, 16 GB eMMC. Armbian_23.02.0/bullseye_5.15.88/server installed.
Any board with enough resource (CPU speed, run time memory, program memory and USB port) is suitable. With this hardware and software configuration, during an audio session, CPU handles one loop in 2-3 ms at 1 GHz.
- Conexant RD02-D400 USB Modem: CX93010 Chipset.
Modem must be a 'Voice Modem', if modem does not support 'Voice Mode' (+FCLASS=8) can not be used.
- Asterisk 16 LTS IP PBX: After default installation, delete all config files and copy only four from project 'asterisk' folder.
If you already have a running IP PBX, you can pass installation steps. If you experienced with Asterisk you can add/remove features. Do not use Playback() routine in dial plan if you want to use hunt group with this project.
- Python3: python3-pip, pyserial modules.
- pstnxsip files: common.py, ip_phone.py, line.py, pstnxsip.py, dial.wav, ringback.wav

# Armbian installation on H96 Mini (Seach internet for more resources)
- !!! Caution, steps below may harm your Android TV and can cause reboot loops or other severe issues !!!
- If you don't know how to restore/programm original H96 Mini Rom, do not forward!

Connect to a TV or monitor your H96 Mini then open and find its IP address.
From https://github.com/ophub/amlogic-s9xxx-armbian/releases download Armbian_23.02.0_amlogic_s905w_bullseye_5.15.XX_server_YYYY.MM.DD.img.
Use proper image tool to prepare SD card or USB memory:
  in Windows systems you can use Rufus
  in Linux systems you can use 'sudo dd if=XXX.img of=/dev/sdX' (X for related disk)
Connect your SD card or USB memory to H96 Mini then find 'Update & Backup' utility in menu and try if it can find the bootloader. If it couldn't try steps below:
  Install android 'adb' utility from Google (Android\Sdk\platform-tools) then run
  'adb connect H96_Mini_IP_address'
  'adb shell' (opens a remote shell)
  'reboot update' (reboots to Armbian)
After reboot, Armbian first config will runs and asks for some parameters. Set a strong root password and add another user if you prefer. Run 'sudo armbian-config' and
  - Change CPU speed to '500-1200' and governor to 'performance'
  - Disable IPV6 support
  - Select Wi-Fi Config and connect to a wi-fi
Exit from armbian-config and reboot to check if Wi-Fi is still working. (Wi-Fi rarely works with Armbian on this android TV models)

(to be continued)

