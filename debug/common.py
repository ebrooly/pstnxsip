# Project: pstnxsip (Python3) (01/01/2023)
# Module: common.py
# Description: Project configuration file.
# Author: Aydin Parin

import time

DEBUGPRINT = True  # print debug messages to default output. (when in service mode in linux systems, system uses service's log file)
# when you use 'undebug.bat' and cleaned all debug lines from code, only errors will be printed to related output even DEBUGPRINT is true.
DEBUGFILE = True  # print debug messages to debug.log file too. (when in service mode in linux systems, system uses service's log file. So, this will be duplicate)
WITHTIME = False  # add time ticker to debug messages  (when in service mode in linux systems, system uses service's log file. So, this will be duplicate)

if (DEBUGFILE):
	debug_log = open(('debug-' + time.strftime('%Y%m%d-%H%M%S') + '.log'), 'w')

def debug(s):
	if (DEBUGPRINT):
		if (WITHTIME):
			print('({: f}) {}'.format(time.time(), s))
		else:
			print(s)
	if (DEBUGFILE):
		if (WITHTIME):
			debug_log.write('({: f}) {}\r\n'.format(time.time(), s))
		else:
			debug_log.write(f'{s}\r\n')
		
def error(s):
	if (WITHTIME):
		print('({: f}) {}'.format(time.time(), s))
	else:
		print(s)
	if (DEBUGFILE):
		if (WITHTIME):
			debug_log.write('({: f}) {}\r\n'.format(time.time(), s))
		else:
			debug_log.write(f'{s}\r\n')

# PhoneState Enum
PS_INACTIVE = 0
PS_REGISTERING = 1
PS_IDLE = 2
PS_DIALING = 3
PS_RINGING = 4
PS_CONNECTED = 5
PS_CANCELING = 6
PS_HANGINGUP = 7
PS_DELETING = 8

# Phone call parameters
RESPONSE_TIMEOUT = 5  # SIP message response and modem AT command response timeout
ANSWER_TIMEOUT = 28  # less than 30 sec, before end points timedout
MAX_SESSION_DURATION = 180	# 3 mins, max session duration (also record duration if RECORDING_ENABLED true
DIAL_TIMEOUT = 30  # when LINE_CAN_DIAL true or an IP Phone dialed pstnxsip internal number directly
ANSWER_AFTER_RINGS = 1  # if pstnxsip is using as a parallel phone and first priority is the hand set, set this parameter accordingly

# IP Phone parameters
REGISTER_EXPIRES = 60

# PSTN Line parameters
MODEM_PORT = '/dev/ttyACM0'  # Modem port for 'serial' module (in Line object)
# when pstnxsip running on linux you can find it in /dev folder using command: ls /dev/ttyA*
# when pstnxsip running on windows you can find it in Device Manager/Com Ports as 'COMX' form
MODEM_COUNTRY_CODE = 'AE'  # country code: 'B5' for US, 'AE' for TR
ECHO_CANCEL_DELTA = 0	# use this two parameters for echo cancellation; 0 disables the echo cancellation (can be deleted all unnecessary codes when disabled)
ECHO_CANCEL_TIME = 0.2  # suppresses audio transmission to IP phone while audio detected from IP Phone

# PSTN_CONNECTOR parameters
LOCAL_PBX = False
if (LOCAL_PBX):
	IP_PBX_USER = '1001'  # PSTNxSIP IP phone (internal) number/user
	IP_PBX_DOMAIN = '192.168.1.110'  # IP address or DNS name (if all clients can resolve DNS name) of IP PBX
	IP_PBX_PASS = '1001'  # PSTNxSIP IP phone password/secret
	IP_PBX_PROXY_ADDRESS = '192.168.1.110'  # Use the same IP_PBX_DOMAIN when no proxy
	IP_PBX_PROXY_PORT = 5060  # SIP port of IP PBX
	CALL_FORWARD_TO = '1000@192.168.1.110'  # used pbx's hunt group option to ring more than one number (see Asterisk's extensions.config)
	# DO NOT USE Playback() routine to anounce dialed number status when using hunt group, because Playback() answers all calls even will not be answered.
	# or DO NOT USE hunt group, use only one number to ring i.e. 1002@192.168.1.110
	LINE_CAN_DIAL = False  # caller from PSTN line can dial an extension when True, redirects call to CALL_FORWARD_TO when False
	IP_PHONE_CID_IS_NUMBER = False  # If you create entries in your phone book like "05552345678" <sip:IP_PBX_USER@IP_PBX_ADDRESS> code will dial out 05552345678 on PSTN line
	IP_PHONE_IP = '192.168.1.111'  # IP address or DNS name of the PSTNxSIP IP phone
	IP_PHONE_PORT = 5060  #  SIP port of the PSTNxSIP IP phone
else:
	IP_PBX_USER = 'your-voip-account-1'  # IP phone username for PSTNxSIP service (account got from VoIP provider, i.e. bob for bob@atlanta.net)
	IP_PBX_DOMAIN = 'your-voip-provider-domain-1'  # IP address or DNS name of VoIP provider's IP PBX (atlanta.net for bob@atlanta.net)
	IP_PBX_PASS = 'password-of-your-voip-account-1'  # IP phone password/secret PSTNxSIP service (account got from VoIP provider)
	IP_PBX_PROXY_ADDRESS = 'your-voip-provider-sip-proxy'  # Use IP_PBX_DOMAIN when no proxy (Use the same proxy for all VoIP clients using same domain)
	IP_PBX_PROXY_PORT = 5060  # SIP port of VoIP provider's Proxy/IP PBX
	CALL_FORWARD_TO = 'your-voip-account-using-in-your-mobile'  # User for Mobile phone's IP Phone App
	LINE_CAN_DIAL = False  # caller from PSTN line can dial an extension when True, redirects call to CALL_FORWARD_TO when False (should be False in this config)
	IP_PHONE_CID_IS_NUMBER = False  # If you create entries in your phone book like "05552345678" <sip:IP_PBX_USER@IP_PBX_ADDRESS> code will dial out 05552345678 on PSTN line
	IP_PHONE_IP = '192.168.1.111'  # IP address or DNS name of the PSTNxSIP IP phone
	IP_PHONE_PORT = 51611  #  SIP port of the PSTNxSIP IP phone
RTP_LOW = 10000
RTP_HIGH = 20000
RTP_LEN = 160  # RTP packet length using when read modem receive buffer in voice mode
RECORDING_ENABLED = False  # if enabled voice records of sessions can be found at the folder where the pstnxsip script running

# loop timing
SAMPLE_FREQ = 8000  # PCMU and PCMA codecs sample frequency, 8000 samples (1 byte -8 bit- per sample) per second
LOOP_TIME = 0.01  # for main loop (10 ms)
CHUNK_SIZE = int(SAMPLE_FREQ * LOOP_TIME)  # file read chunk length depends on loop time and sample rate (8000)

DTMF_DIGITS = '0123456789*#ABCD'
