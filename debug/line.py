# Project: pstnxsip (Python3) (01/01/2023)
# Module: line.py
# Description: PSTN Line handler of pstnxsip. Controls USB modem connected to PSTN line.
# Author: Aydin Parin (Code inspired/altered from https://github.com/pradeesi/ play_audio_over_phone_line, record_audio_from_phone_line)

from ip_phone import IPPhone
import common
import serial
import time
import atexit

debug = common.debug

# Modem / Phone line handler parameters
RING_TIMEOUT = 7  # timeout beetween two rings, if caller give up/cancel call

# Modem AT Command Set
FACTORY_RESET = 'ATZ\r\n'.encode('ascii')
SET_COUNTRY = ('AT+GCI=' + common.MODEM_COUNTRY_CODE + '\r\n').encode('ascii')  # set country to TR
ECHO_OFF = 'ATE0\r\n'.encode('ascii')
ENABLE_FORMATTED_CID = 'AT+VCID=1\r\n'.encode('ascii')
CALL_WAITING_ENABLE = 'AT+PCW=0\r\n'.encode('ascii')
REPORT_CID = 'AT+VRID=0\r\n'.encode('ascii')
ENABLE_VERBOSE_CODES = 'ATV1\r\n'.encode('ascii')
ENTER_DATA_MODE = 'AT+FCLASS=0\r\n'.encode('ascii')
ENTER_VOICE_MODE = 'AT+FCLASS=8\r\n'.encode('ascii')
ENTER_VOICE_TRANSMIT_RECIEVE_STATE = 'AT+VTR\r\n'.encode('ascii')	# Start Voice Transmission and Reception (Voice Duplex)
SEND_DTMF = 'AT+VTS='
SET_VOICE_COMPRESSION = 'AT+VSM=1,8000,0,0\r\n'.encode('ascii')  # 1 = 8-bit unsigned pcm, 8.0 kHz
LINE_OFF_HOOK = 'AT+VLS=1\r\n'.encode('ascii')  # DCE off-hook, connected to telco
LINE_ON_HOOK = 'AT+VLS=0\r\n'.encode('ascii')   # DCE on-hook
RECEIVE_GAIN = 'AT+VGR=255\r\n'.encode('ascii') # Gain Receive (Record Gain)
TRANSMIT_GAIN = 'AT+VGT=128\r\n'.encode('ascii') # Gain Transmit (Playback Volume)
DTMF_DURATION = 'AT+VTD=30\r\n'.encode('ascii')  # DTMF duration set to 300 ms
TERMINATE_CALL = 'ATH\r\n'.encode('ascii')

# Modem DLE shielded codes - DCE to DTE modem data
DLE_CHAR = 16					# <DLE>
DLE_ERASER = 17					# to erase <DLE> from buffer
DCE_BUSY_TONE = 98				# <DLE>-b
DCE_SILENCE_DETECTED = 115		# <DLE>-s
DCE_TX_BUFFER_UNDERRUN = 117	# <DLE>-u
DCE_RX_BUFFER_OVERRUN = 111		# <DLE>-o
DCE_END_VOICE_DATA_TX = 3		# <DLE><ETX>

# Supported <DLE> Shielded Codes Sent to the Modem (DCE) (not in the table, from pdf)
DTE_END_VOICE_DATA_TX_RX = (chr(16) + chr(94)).encode('ascii')	# <DLE>^

# Modem reply strings
OK_STR = 'OK\r\n'.encode('ascii')
ERROR_STR = 'ERROR\r\n'.encode('ascii')
CONNECT_STR = 'CONNECT\r\n'.encode('ascii')
RING_STR = 'RING\r\n'.encode('ascii')
DATE_STR = 'DATE'.encode('ascii')
TIME_STR = 'TIME'.encode('ascii')
NMBR_STR = 'NMBR'.encode('ascii')
DCE_END_VOICE_DATA_TX_RESP = (chr(16) + chr(3)).encode('ascii')

class Line:
	def __init__(self, usb_port: str):
		# Modem / serial port itial values
		self.modem = serial.Serial()
		self.modem.port = usb_port
		self.modem.baudrate = 115200
		self.modem.bytesize = serial.EIGHTBITS	#number of bits per bytes
		self.modem.parity = serial.PARITY_NONE	#set parity check: no parity
		self.modem.stopbits = serial.STOPBITS_ONE	#number of stop bits
		self.modem.timeout = 0					#non-block read
		self.modem.xonxoff = False				#disable software flow control
		self.modem.rtscts = False					#disable hardware (RTS/CTS) flow control
		self.modem.dsrdtr = False					#disable hardware (DSR/DTR) flow control
		self.modem.writeTimeout = 0				#timeout for write
		self.state = common.PS_INACTIVE
		self.modem_response = bytes('', 'ascii')
		self.caller_id = ''
		self.dtmf = ''
		self.m_val = 128
		self.echo_cancel = 0
		self.ring_counter = 0
		self.ring_timer = 0
		self.status = None
		debug(':line.init: Modem initialized.')

	def start(self) -> None:
		if (self.modem.is_open):
			self.modem.close()
			time.sleep(1)
		self.modem.open()  # Open Serial Port
		self.modem.reset_input_buffer()
		self.modem.reset_output_buffer()
		self.command(TERMINATE_CALL, OK_STR)  # hang-up if opened
		self.command(FACTORY_RESET, OK_STR)  # reset to factory default.
		self.command(ECHO_OFF, OK_STR)  # Disable Command Echo Mode.
		self.command(SET_COUNTRY, OK_STR)  # set country.
		self.command(ENABLE_VERBOSE_CODES, OK_STR)  # Display result codes in verbose form 	
		self.command(ENTER_DATA_MODE, OK_STR)  # Enter Data Mode
		self.command(ENABLE_FORMATTED_CID, OK_STR)  # Enable formatted caller report.
		self.command(CALL_WAITING_ENABLE, OK_STR)  # Enable call waiting for CID.
		self.state = common.PS_IDLE
		debug(':line.start: line.state: PS_IDLE')

	def stop(self) -> None:
		if (self.modem.is_open):
			self.modem.close()
		self.state = common.PS_INACTIVE
		debug(':line.stop: line.state: PS_INACTIVE')

	def command(self, cmd, resp='') -> None:
		result = False
		self.modem_response = bytes('', 'ascii')
		self.modem.write(cmd)  # Send command to the Modem
		self.status = None  # clear status
		debug(f':line.command: sent: {cmd}')
		if (resp == ''):
			return
		timeout = time.time() + common.RESPONSE_TIMEOUT
		while (time.time() < timeout):
			if (self.modem.in_waiting != 0): # if response
				self.modem_response += self.modem.read(self.modem.in_waiting)
			if (resp in self.modem_response):
				result = True
				break
			elif (ERROR_STR in self.modem_response):
				result = False
				break
		debug(f':line.command: rcvd: {self.modem_response}')  # do not clear modem response here
		if (result == False):  # Failed command execution
			common.error(':line.command: Error! Modem AT Command Response Error or Timeout.')

	def start_voice_mode(self) -> None:
		if (self.state != common.PS_CONNECTED):
			self.command(ENTER_VOICE_MODE, OK_STR)  # Enter Voice Mode
			self.command(DTMF_DURATION, OK_STR)  # Set DTMF duration.
			self.command(RECEIVE_GAIN, OK_STR)  # Set receive gain.
			self.command(TRANSMIT_GAIN, OK_STR)  # Set transmit gain.
			self.command(SET_VOICE_COMPRESSION, OK_STR)  # Compression Method: Unsigned PCM / Sampling Rate: 8000MHz
			self.command(LINE_OFF_HOOK, OK_STR)  # Open line
			self.command(ENTER_VOICE_TRANSMIT_RECIEVE_STATE, CONNECT_STR)  # Put modem into voice transmit receive mode
		self.caller_id = ''
		self.dtmf = ''
		self.m_val = 128
		self.echo_cancel = 0
		self.ring_counter = 0
		self.ring_timer = 0
		self.state = common.PS_CONNECTED
		debug(':line.start_voice_mode: line.state: CONNECTED')

	def stop_voice_mode(self) -> None:
		self.modem.reset_input_buffer()
		self.modem.reset_output_buffer()
		if ((self.state == common.PS_CONNECTED) or (self.state == common.PS_HANGINGUP)):
			self.command(DTE_END_VOICE_DATA_TX_RX, DCE_END_VOICE_DATA_TX_RESP)  # Send End of Voice Transmit Recieve
			self.command(LINE_ON_HOOK, OK_STR)
			self.command(TERMINATE_CALL, OK_STR)
		self.command(ENTER_DATA_MODE, OK_STR)  # Enter Data Mode
		self.command(ENABLE_FORMATTED_CID, OK_STR)  # Enable formatted caller report.
		self.command(CALL_WAITING_ENABLE, OK_STR)  # Enable call waiting for CID.
		self.caller_id = ''
		self.dtmf = ''
		self.m_val = 128
		self.echo_cancel = 0
		self.ring_counter = 0
		self.ring_timer = 0
		self.state = common.PS_IDLE
		debug(':line.stop_voice_mode: line.state: PS_IDLE')

	def handler(self) -> None:
		if (self.state != common.PS_CONNECTED):  # if modem in data mode
			if (self.modem.in_waiting > 0):  # check if modem has data
				self.modem_response += self.modem.read(self.modem.in_waiting)
				if (len(self.modem_response) != 0):
					debug(f':line_handler: Modem response: {self.modem_response}')
					if (RING_STR in self.modem_response):  # call incoming from line
						self.ring_timer = time.time() + RING_TIMEOUT  # every ring restarts timer
						self.ring_counter += 1  # increase ring counter
						if (self.state != common.PS_RINGING):
							self.state = common.PS_RINGING
							time.sleep(0.5)  # wait a while
							self.command(REPORT_CID, OK_STR)  # request caller ID
							# self.caller_id = 'PSTNxSIP'  # delete this and get CID from modem response
							if (DATE_STR in self.modem_response) or (TIME_STR in self.modem_response) or (NMBR_STR in self.modem_response):  # if caller ID
								# self.caller_id = 'PSTNxSIP'  # delete this and get CID from modem response
								debug(f':line.handler:  {self.caller_id} calling.')
								pass
							self.modem_response = bytes('', 'ascii')  # clear response
					elif (OK_STR in self.modem_response):  # if unhandled response
						self.modem_response = bytes('', 'ascii')  # clear response
			elif (self.ring_timer != 0):
				if (time.time() > self.ring_timer):  # Call from line, Caller give up / cancel
					debug(':main_handler: Warning! Caller gived up / canceled. Call will be disconnected.')
					self.state = common.PS_IDLE

	def read_audio(self) -> bytes:  # Modem Receive
		pstn_read = None
		if (self.state == common.PS_CONNECTED):  # if modem in voice mode
			if (self.modem.in_waiting >= common.RTP_LEN):  # if modem receive buffer has data
				pstn_read = bytearray(self.modem.read(self.modem.in_waiting))  # read modem receive buffer
				data_len = len(pstn_read)
				dle = pstn_read.find(DLE_CHAR)  # if <DLE>s in audio data
				while (dle >= 0):  # if DLE char found
					pstn_read[dle] = DLE_ERASER  # change with DLE_ERASER
					dle += 1  # search for a code in the next byte
					if (dle == data_len):  # no more bytes in data
						break
					if (pstn_read[dle] == DLE_CHAR):  # will be deleted
						pass
					elif (pstn_read[dle] == DCE_BUSY_TONE):
						debug(':line.read_audio: Warning! Busy tone detected. Call will be disconnected.')
						self.state = common.PS_HANGINGUP
						break
					elif (pstn_read[dle] == DCE_SILENCE_DETECTED):
						debug(':line.read_audio: Warning! Silence detected. Call will be disconnected.')
						self.state = common.PS_HANGINGUP
						break
					elif (pstn_read[dle] == DCE_END_VOICE_DATA_TX):
						debug(':line.read_audio: Warning! <DLE><ETX> Char recieved. Call will be disconnected.')
						self.state = common.PS_HANGINGUP
						break
					elif (pstn_read[dle] == DCE_TX_BUFFER_UNDERRUN):  # <DLE>u : transmit buffer underrun
						self.status = DCE_TX_BUFFER_UNDERRUN
						debug(':line.read_audio: Warning! TX Buffer Underrun.')
						pass
					elif (pstn_read[dle] == DCE_RX_BUFFER_OVERRUN):  # <DLE>o : receive buffer overrun
						debug(':line.read_audio: Warning! RX Buffer Overrun.')
						pass
					elif (chr(pstn_read[dle]) in common.DTMF_DIGITS):  # DTMF tone received from line
						self.dtmf = chr(pstn_read[dle])
						debug(f':line.read_audio: DTMF tone {self.dtmf} recieved from line.')
					else:
						debug(f':line.read_audio: Unhandled <DLE><0x{hex(pstn_read[dle])}> recieved.')  # <DLE><code> received
						pass
					pstn_read[dle] = DLE_ERASER
					dle = pstn_read.find(DLE_CHAR, dle)  # dle intentionally not increased
		return pstn_read

	def write_audio(self, packet: bytes) -> None:  #Modem Transmit
		if (self.state == common.PS_CONNECTED):  # if modem in voice mode
			if (self.modem.out_waiting < 6401):  # if modem transmit buffer has space (out_waiting returns wrong numbers, sometimes multiplied by 8 sometimes 16)
				data = bytearray(packet)  # read IP call receive buffer
				data_len = len(data)
				if (data_len != 0):  # if data received and modem buffer has space (out_waiting parameter returns wrong numbers)
					dle = data.find(DLE_CHAR)  # if <DLE>s in audio data
					while (dle >= 0):  # if DLE char found
						data[dle] = DLE_ERASER  # change with DLE_ERASER
						dle = data.find(DLE_CHAR, dle)  # dle intentionally not increased
					if (common.ECHO_CANCEL_DELTA != 0):  # 'echo cancellation' handling
						i = j = m = 0
						while (i < data_len):
							v = data[i]
							if (v > 128):  # only positive values (audio packets consist: 8 bit, unsigned, 0x80 biased)
								m += int(v)  # m: sum of ip_read bytes
								j += 1
								if (j == 10):  # 10 sample to detect sound changes
									break
							i += 1
						if (j > 0):  # if sound detected
							m = m / j  # calculate mean value of samples
							if (abs(self.m_val - m) > common.ECHO_CANCEL_DELTA):  # if mean value changes above limit
								self.echo_cancel = time.time() + common.ECHO_CANCEL_TIME  # (re)trigger echo cancellation timer
							self.m_val = int((self.m_val + m) / 2)  # calculate long term mean value
							if (self.m_val > (128 + common.ECHO_CANCEL_DELTA)):  # if mean value is high enough
								self.echo_cancel = time.time() + common.ECHO_CANCEL_TIME  # (re)trigger echo cancellation timer
						if (self.echo_cancel != 0):  # during echo cancellation time
							if (time.time() > self.echo_cancel):  # timeout occured
								self.echo_cancel = 0  # end echo cancellation
					self.modem.write(data)  # send packet
					if (self.status == DCE_TX_BUFFER_UNDERRUN):
						self.modem.write(data)  # add the same packet to transmit queue
						self.status = None  # clear status

	def read_dtmf(self) -> str:
		dtmf = self.dtmf
		self.dtmf = ''
		return dtmf

	def send_dtmf(self, dtmf: str) -> None:
		self.modem.write((SEND_DTMF + dtmf + '\r\n').encode('ascii'))  # Send DTMF tone to line
		debug(f':line.send_dtmf: DTMF {dtmf} sent to line.')
		
	def dial(self, number: str) -> None:
		self.command(('ATD' + number + ';\r\n').encode('ascii'), OK_STR)  # Dial PBX number
		debug(f':line.dial:  {number} dialed.')

	def read_caller_id(self) -> str:
		return self.caller_id

