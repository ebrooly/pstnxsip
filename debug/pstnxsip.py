# Project: pstnxsip (Python3) (01/01/2023)
# Module: pstnxsip.py 
# Description: Main handler of pstnxsip. Controls PSTN line and IP Phone calls. 
# Author: Aydin Parin

from ip_phone import IPPhone
from line import Line
import common
import serial
import time
import atexit
import wave

debug = common.debug

FROM_IP = 1
FROM_PSTN = 2

cross_connected = False
call_from = None
dial_timer = 0
session_timer = 0
resp_timer = 0
line_number = ''
ip_number = ''
play_started = False
play_file = None
total_chunk = 0
chunk_counter = 0
rec_started = False
rec_file = None
ip_phone: IPPhone = None
line: Line = None

def start_cross_conn() -> None:
	global cross_connected, ip_phone, line, line_number, ip_number, session_timer, dial_timer, resp_timer
	debug(':start_cross_conn: ...')
	if (cross_connected):  # if modem already in Voice Mode
		return
	stop_play_file()
	if (common.RECORDING_ENABLED):
		start_record_file(line_number, ip_number)
	line.start_voice_mode()
	audio_data = ip_phone.read_audio()  # empty IP call receive buffer
	audio_data = line.read_audio()  # empty modem receive buffer
	session_timer = time.time() + common.MAX_SESSION_DURATION
	dial_timer = 0
	resp_timer = 0
	cross_connected = True

def stop_cross_conn() -> None:
	global cross_connected, ip_phone, line, line_number, ip_number, session_timer, dial_timer, resp_timer, call_from
	debug(':stop_cross_conn: ...')
	line.stop_voice_mode()
	ip_phone.hangup()
	stop_play_file()
	if (common.RECORDING_ENABLED):
		stop_record_file()
	line_number = ''
	ip_number = ''
	session_timer = 0
	dial_timer = 0
	resp_timer = 0
	call_from = None
	cross_connected = False

def start_play_file(file_name: str) -> None:
	global play_started, play_file, total_chunk, chunk_counter
	if (not play_started):
		play_file = wave.open(file_name,'rb')
		total_chunk = play_file.getnframes() / common.CHUNK_SIZE
		chunk_counter = 0
		play_started = True
		debug(f':start_play_file: {file_name} playing')

def play_handler() -> None:
	global play_started, play_file, total_chunk, chunk_counter, call_from, ip_phone, line
	if (play_started):
		if (chunk_counter < total_chunk):
			if (call_from == FROM_PSTN):
				line.write_audio(play_file.readframes(common.CHUNK_SIZE))
			elif (call_from == FROM_IP):
				ip_phone.write_audio(play_file.readframes(common.CHUNK_SIZE))
			chunk_counter += 1
		else:
			stop_play_file()

def stop_play_file() -> None:
	global play_started, play_file
	if (play_started):
		play_file.close()
		play_started = False
		debug(f':stop_play_file: ...')

def start_record_file(line_num: str, ip_num: str) -> None:
	global rec_started, rec_file
	line_num = line_num.strip('*#ABCD')
	if (line_num == ''):
		line_num = 'X'
	ip_num = ip_num.strip('*#ABCD')
	if (ip_num == ''):
		ip_num = 'X'
	if (not rec_started):
		if (call_from == FROM_PSTN):
			file_name = time.strftime('%Y%m%d-%H%M%S') + '_' + line_num + '_to_' + ip_num + '.wav'
		elif (call_from == FROM_IP):
			file_name = time.strftime('%Y%m%d-%H%M%S') + '_' + ip_num + '_to_' + line_num + '.wav'
		rec_file = wave.open(file_name, 'wb')
		rec_file.setnchannels(1)
		rec_file.setsampwidth(1)
		rec_file.setframerate(common.SAMPLE_FREQ)
		rec_started = True
		debug(f':start_record_file: {file_name} recording')

def record_handler(audio_data: bytes = []) -> None:
	global rec_started, rec_file
	if (rec_started):
		rec_file.writeframes(audio_data)

def stop_record_file() -> None:
	global rec_started, rec_file
	if (rec_started):
		rec_file.close()
		rec_started = False
		debug(f':stop_record_file: ...')

def close_connections() -> None:
	global ip_phone, line
	debug(':close_connections: ...')
	stop_cross_conn()
	if (ip_phone.state != common.PS_INACTIVE):
		ip_phone.stop()
		while (ip_phone.state != common.PS_INACTIVE):
			ip_phone.handler()
	line.stop()
	if (common.DEBUGFILE):  # if debug.log file opened
		common.debug_log.close()  # close debug.log file

def main_handler() -> None:
	global session_timer, resp_timer, dial_timer, cross_connected, call_from, ip_phone, line, line_number, ip_number

	if (cross_connected):  # if modem in 'Voice Mode'
		if (time.time() > session_timer):  # handle session timeout, if call session timeout (default 3 mins)
			debug(':main_handler: Warning! Session timeout occured. Call will be disconnected.')
			stop_cross_conn()
		elif (ip_phone.state == common.PS_IDLE):
			debug(':main_handler: IP phone closed the call.-1')
			stop_cross_conn()
		elif (line.state != common.PS_CONNECTED):
			debug(':main_handler: Line closed the call.')
			stop_cross_conn()
		else:
			line_read = line.read_audio()  # handle modem receive buffer, read modem receive buffer
			if (line_read != None):
				if (common.RECORDING_ENABLED):
					record_handler(line_read)
				if (line.echo_cancel != 0):
					ip_phone.write_audio(b'\x80' * len(line_read))  # send 'silence' to IP phone (audioop routines can be used for suppression)
				else:
					ip_phone.write_audio(line_read)  # send audio to IP phone
			ip_read = ip_phone.read_audio()  # handle IP call receive buffer, read IP call receive buffer
			if (ip_read != None):
				line.write_audio(ip_read)  # write data to modem buffer
			dtmf = line.read_dtmf()	# handle DTMF from PSTN, last pressed key
			if ((dtmf != '') and (dtmf in common.DTMF_DIGITS)):  # DTMF tone from PSTN, send DTMF code to IP phone
				ip_phone.send_dtmf(dtmf)
			dtmf = ip_phone.read_dtmf()	# handle DTMF from IP, last pressed key
			if ((dtmf != '') and (dtmf in common.DTMF_DIGITS)):  # DTMF tone from IP phone, send DTMF code to PSTN
				line.send_dtmf(dtmf)
	elif (call_from == FROM_IP):  # handle call initiated from IP
		audio_data = ip_phone.read_audio()  # empty IP phone receive buffer
		audio_data = line.read_audio()  # empty line receive buffer
		if (ip_phone.state == common.PS_IDLE):  # call hanged-up
			debug(':main_handler: IP phone closed the call.-2')
			stop_cross_conn()
			return
		if (ip_phone.state == common.PS_CONNECTED):  #  call connected
			if (dial_timer == 0):  # IP call connected, will be waiting for IP phone to dial a number
				debug(':main_handler: IP call connected.')
				resp_timer = 0
				line_number = ''
				dial_timer =  time.time() + common.DIAL_TIMEOUT
				start_play_file('dial.wav')
				return
			if (time.time() > dial_timer):  # if IP phone not dialed a number (timeout)
				debug(':main_handler: Warning! IP phone not dialed a number. Call will be disconnected.')
				stop_cross_conn()  # even if not started (initializes all parameters)
				return
			dtmf = ip_phone.read_dtmf()	# last pressed key
			if ((dtmf != '') and (dtmf in common.DTMF_DIGITS)):  # get digits
				line_number += dtmf
				# modify this lines; can create a dial plan or restrict dialing numbers (for outbound calls)
				num_digit = 4
				if (line_number[0] == '0'):  # can dial outside i.e. 05552345678
					num_digit = 11
				elif (line_number[0] == '*'):  # this is for internal numbers used in this project
					num_digit = 3
				else:
					debug(':main_handler: Warning! IP phone dialed a wrong number. Call will be disconnected.')
					stop_cross_conn()  # even if not started (initializes all parameters)
					return
				if (len(line_number) == num_digit):  # if n digit pressed
					line.dial(line_number)
					start_cross_conn()
					return
		if (resp_timer != 0):
			if (time.time() > resp_timer):
				debug(f':main_handler: Warning! IP phone connect timeout occured. Call will be disconnected. {ip_phone.call_id}')
				resp_timer = 0
				ip_phone.hangup()
	elif (call_from == FROM_PSTN):  # handle call initiated from PSTN
		audio_data = ip_phone.read_audio()  # empty IP phone receive buffer
		audio_data = line.read_audio()  # empty line receive buffer
		if (line.state != common.PS_CONNECTED):  # PSTN line session disconnected
			debug(':main_handler: Line gived-up.')
			stop_cross_conn()
			return
		if (ip_phone.state == common.PS_CONNECTED):  # Call answered
			debug(':main_handler: IP phone answered, call connected.')
			start_cross_conn()
			return
		if (resp_timer != 0):
			if (time.time() > resp_timer):  # Call not answered
				debug(':main_handler: Dialed IP phone, answer timeout occured.')
				stop_cross_conn()
				return
			elif (ip_phone.state == common.PS_IDLE):  # Call rejected/busy
				debug(':main_handler: IP phone rejected call/busy.')
				stop_cross_conn()
				return
		if (dial_timer != 0):  # IP call connected, will be waiting for PSTN phone to dial a number (if can dial)
			if (time.time() > dial_timer):  # if Line not dialed a number (timeout)
				debug(':main_handler: Warning! PSTN phone not dialed a number. Call will be disconnected.')
				stop_cross_conn()  # even if not started (initializes all parameters)
				return
			dtmf = line.read_dtmf()	# last pressed key
			if ((dtmf != '') and (dtmf in common.DTMF_DIGITS)):  # get digits
				ip_number += dtmf
				# modify this lines when LINE_CAN_DIAL = True; can create an IVR menu or a dial plan or restrict dialing numbers (for inbound calls)
				num_digit = 4
				if (ip_number[0] == '1'):  # if number starts with 1
					if ((len(ip_number) == num_digit) and (ip_phone.state == common.PS_IDLE)):  # if n digit pressed
						ip_number = f'{ip_number}@{common.IP_PBX_DOMAIN}'
						debug(f':main_handler: Line dialed IP phone {ip_number}.')
						dial_timer = 0
						resp_timer = time.time() + common.ANSWER_TIMEOUT
						start_play_file('ringback.wav')
						ip_phone.call(line_number, ip_number)	 # call IP phone
				else:
					debug(':main_handler: Warning! PSTN phone dialed a wrong number. Call will be disconnected.')
					stop_cross_conn()  # even if not started (initializes all parameters)
	elif (ip_phone.state == common.PS_RINGING):  # wait for a call initiated from IP, ringing started from IP
		debug(':main_handler: Answer incoming IP call.')
		resp_timer = time.time() + common.RESPONSE_TIMEOUT
		call_from = FROM_IP
		ip_phone.answer()
	elif (line.state == common.PS_RINGING):
		if (line.ring_counter == common.ANSWER_AFTER_RINGS):  # wait for a call initiated from line
			debug(':main_handler: Answer incoming Line call.')
			line_number = line.read_caller_id()  # get caller ID
			call_from = FROM_PSTN
			line.start_voice_mode()
			if ((common.LOCAL_PBX) and (common.LINE_CAN_DIAL)):  # inbound PSTN calls can dial only when LOCAL_PBX and LINE_CAN_DIAL are True
				ip_number = ''
				dial_timer =  time.time() + common.DIAL_TIMEOUT
				start_play_file('dial.wav')
			else:
				resp_timer = time.time() + common.ANSWER_TIMEOUT
				start_play_file('ringback.wav')
				ip_number = common.CALL_FORWARD_TO
				ip_phone.call(line_number, ip_number)  # call IP phone

if __name__ == '__main__':
	atexit.register(close_connections)

	line = Line(common.MODEM_PORT)
	line.start()
	ip_phone = IPPhone(common.IP_PBX_USER, common.IP_PBX_DOMAIN, common.IP_PBX_PASS, common.IP_PHONE_IP, common.IP_PHONE_PORT, \
		common.RTP_LOW, common.RTP_HIGH, common.IP_PBX_PROXY_ADDRESS, common.IP_PBX_PROXY_PORT)
	ip_phone.start()
	while(ip_phone.state == common.PS_REGISTERING):
		ip_phone.handler()
		time.sleep(0.1)

while(True):
	start_time = time.time()
	if (ip_phone.state == common.PS_INACTIVE):
		common.error('Error!: IP PBX deregistered ip_phone.')
		exit()
	main_handler()
	line.handler()
	ip_phone.handler()
	play_handler()
	delta = time.time() - start_time  # try to stabilize loop time
	if (delta < common.LOOP_TIME):
		time.sleep(common.LOOP_TIME - delta)
	else:
		time.sleep(common.LOOP_TIME)
