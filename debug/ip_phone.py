# Project: pstnxsip (Python3) (01/01/2023)
# Module: ipphone.py
# Description: IP Phone (SIP-RTP) handler of pstnxsip. IP Phone client based on SIP and RTP protocols over UDP.
# Author: Aydin Parin (Code inspired/altered from https://github.com/tayler6000/pyVoIP)

from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Union, Tuple
import common
import hashlib
import random
import time
import uuid
import socket
import select
import audioop
import re

__all__ = [
	'SIPMessage',
	'IPPhone'
]

debug = common.debug

# SIP parameters
DEF_SIP_PORT = 5060
SIP_BUF_SIZE = 4096
SIPMethods = ['INVITE', 'ACK', 'BYE', 'CANCEL', 'REGISTER', 'OPTIONS', 'PRACK', 'SUBSCRIBE', 'NOTIFY', 'PUBLISH', 'INFO', 'REFER', 'MESSAGE', 'UPDATE']
SIPCompatibleMethods = ['INVITE', 'ACK', 'BYE', 'CANCEL']
SIPCompatibleVersions = ['SIP/2.0']
SIP_REQUEST = 1
SIP_RESPONSE = 2

# RTP parameters
RTP_PACKET_MAX_SIZE = 1440

# RTP codecs Enum
PCMU = 0
PCMA = 8
EVENT = 101
rtp_maps: Dict = {PCMU: ['PCMU', 8000, 1],
				PCMA: ['PCMA', 8000, 1],
				EVENT: ['telephone-event', 8000, 1]}

# SIP Message Enum
SS_TRYING = 100
SS_PUSH_SENT = 110
SS_RINGING = 180
SS_TERMINATED = 199
SS_OK = 200
SS_BAD_REQUEST = 400
SS_UNAUTHORIZED = 401
SS_FORBIDDEN = 403
SS_NOT_FOUND = 404
SS_PROXY_AUTHENTICATION_REQUIRED = 407
SS_REQUEST_TIMEOUT = 408
SS_TEMPORARILY_UNAVAILABLE = 480
SS_CALL_OR_TRANSACTION_DOESNT_EXIST = 481
SS_BUSY_HERE = 486
SS_REQUEST_TERMINATED = 487
SS_INTERNAL_SERVER_ERROR = 500
SS_NOT_IMPLEMENTED = 501
SS_SERVICE_UNAVAILABLE = 503
SS_DECLINE = 603
SS_UNKNOWN = 999
sip_status: Dict = { SS_TRYING: 'Trying',
					SS_PUSH_SENT: 'Push sent',
					SS_RINGING: 'Ringing',
					SS_TERMINATED: 'Early Dialog Terminated',
					SS_OK: 'OK',
					SS_BAD_REQUEST: 'Bad Request',
					SS_UNAUTHORIZED: 'Unauthorized',
					SS_FORBIDDEN: 'Forbidden',
					SS_NOT_FOUND: 'Not Found',
					SS_PROXY_AUTHENTICATION_REQUIRED: 'Proxy Authentication Required',
					SS_REQUEST_TIMEOUT: 'Request Timeout',
					SS_TEMPORARILY_UNAVAILABLE: 'Temporarily Unavailable',
					SS_CALL_OR_TRANSACTION_DOESNT_EXIST: 'Call/Transaction Does Not Exist',
					SS_BUSY_HERE: 'Busy Here',
					SS_REQUEST_TERMINATED: 'Request Terminated',
					SS_INTERNAL_SERVER_ERROR: 'Internal Server Error',
					SS_NOT_IMPLEMENTED: 'Not Implemented',
					SS_SERVICE_UNAVAILABLE: 'Service Unavailable',
					SS_DECLINE: 'Declined',
					SS_UNKNOWN: 'Unknown'}

class SIPMessage:
	def __init__(self, data: bytes):
		self.heading = b''
		self.msg_type = None
		self.version = ''
		self.method = ''
		self.status = ''
		self.headers: Dict[str, Any] = {}
		self.body: Dict[str, Any] = {}
		self.authentication: Dict[str, str] = {}
		self.auth_match = re.compile('(\w+)=("[^",]+"|[^ \t,]+)')
		self.parse(data)

	def parse(self, data: bytes) -> None:

		headers = []
		body = []
		if (data.find(b'\r\n\r\n') < 0):  # Unknown or corrupt SIP Message
			self.msg_type = None
			return

		if (len(data) > (data.find(b'\r\n\r\n') + 4)):  # chek if body exist
			headers, body = data.split(b'\r\n\r\n')
		else:
			headers = data.split(b'\r\n\r\n')[0]
	
		headers_raw = headers.split(b'\r\n')
		self.heading = headers_raw.pop(0)
		check = str(self.heading.split(b' ')[0], 'utf8')
		if (check in SIPMethods):
			self.msg_type = SIP_REQUEST
			self.version = str(self.heading.split(b' ')[2], 'utf8')
			self.method = str(self.heading.split(b' ')[0], 'utf8')
		else:
			self.msg_type = SIP_RESPONSE
			self.version = str(self.heading.split(b' ')[0], 'utf8')
			self.status = SS_UNKNOWN
			status = int(self.heading.split(b' ')[1])
			if (status in sip_status):
					self.status = status

		if (self.version not in SIPCompatibleVersions):
			return

		for h in headers_raw:
			s = str(h, 'utf8').split(': ')
			self.parse_header(s[0], s[1])

		if ('Content-Encoding' in self.headers):
			error(':SIP.parse: Error! Unable to parse encoded content.')
			msg.msg_type = None
			return

		if (len(body) > 0):
			if (self.headers['Content-Type'] != 'application/sdp'):  # Referenced RFC 4566 July 2006
				self.body = body
				return
			body_raw = body.split(b'\r\n')
			for x in body_raw:
				i = str(x, 'utf8').split('=')
				if (i != ['']):
					self.parse_body(i[0], i[1])

	def parse_header(self, header: str, data: str) -> None:
		if (header == 'Via'):
			if ('Via' not in self.headers):
				self.headers['Via'] = []
			info = re.split(' |;', data)
			_type = info[0]  # SIP Method
			_address = info[1].split(':')  # Tuple: address, port
			_ip = _address[0]
			if (len(_address) > 1):
				_port = int(_address[1])
			else:
				_port = DEF_SIP_PORT
			_via = {'type': _type, 'address': (_ip, _port)}
			for x in info[2:]:
				if ('=' in x):
					_via[x.split('=')[0]] = x.split('=')[1]
				else:
					_via[x] = None
			self.headers['Via'].append(_via)
		elif (header == 'Record-Route'):
			if ('Record-Route' not in self.headers):
				self.headers['Record-Route'] = []
			self.headers['Record-Route'].append(data)
		elif (header == 'Route'):
			if ('Route' not in self.headers):
				self.headers['Route'] = []
			self.headers['Route'].append(data)
		elif ((header == 'From') or (header == 'To')):
			info = data.split(';tag=')
			tag = ''
			if (len(info) >= 2):
				tag = info[1]
			raw = info[0]
			contact = re.split(r'<?sip:', raw)
			cid = contact[0].strip(' ')
			cid = cid.strip('\"')
			cid = cid.strip("\'")
			address = contact[1].strip('>')
			if (len(address.split('@')) == 2):
				user = address.split('@')[0]
				host = address.split('@')[1]
			else:
				user = None
				host = address
			self.headers[header] = {'raw': raw, 'address': address, 'cid': cid, 'user': user, 'host': host, 'tag': tag}
		elif (header == 'CSeq'):
			self.headers[header] = {'check': data.split(' ')[0], 'method': data.split(' ')[1]}
		elif ((header == 'Allow') or (header == 'Supported')):
			self.headers[header] = data.split(', ')
		elif (header == 'Content-Length'):
			self.headers[header] = int(data)
		elif ((header == 'WWW-Authenticate') or (header == 'Proxy-Authenticate')):
			data = data.replace('Digest ', '')
			row_data = self.auth_match.findall(data)
			header_data = {}
			for var, data in row_data:
				header_data[var] = data.strip('"')
			self.headers[header] = header_data
			self.authentication = header_data
		else:
			self.headers[header] = data

	def parse_body(self, header: str, data: str) -> None:
		if (header == 'v'):  # SDP 5.1 Version
			self.body[header] = int(data)
		elif (header == 'o'):  # SDP 5.2 Origin, o=<username> <sess-id> <sess-version> <nettype> <addrtype> <unicast-address> # noqa: E501
			d = data.split(' ')
			self.body[header] = {'username': d[0], 'id': d[1], 'version': d[2], 'network_type': d[3], 'address_type': d[4], 'address': d[5] }
		elif (header == 's'):  # SDP 5.3 Session Name, s=<session name>
			self.body[header] = data
		elif (header == 'i'):  # SDP 5.4 Session Information, i=<session-description>
			self.body[header] = data
		elif (header == 'u'):  # SDP 5.5, URI u=<uri>
			self.body[header] = data
		elif ((header == 'e') or (header == 'p')):  # SDP 5.6 Email Address and Phone Number of person responsible for the conference, e=<email-address> p=<phone-number>
			self.body[header] = data
		elif (header == 'c'):  # SDP 5.7 Connection Data, c=<nettype> <addrtype> <connection-address>
			d = data.split(' ')
			self.body[header] = {'network_type': d[0], 'address_type': d[1], 'address': d[2]}
		elif (header == 'b'):  # SDP 5.8 Bandwidth b=<bwtype>:<bandwidth>
			d = data.split(':')
			self.body[header] = {'type': d[0], 'bandwidth': d[1]}
		elif (header == 't'):  # SDP 5.9 Timing t=<start-time> <stop-time>
			d = data.split(' ')
			self.body[header] = {'start': d[0], 'stop': d[1]}
		elif (header == 'r'):  # SDP 5.10 Repeat Times r=<repeat interval> <active duration> <offsets from start-time> # noqa: E501
			d = data.split(' ')
			self.body[header] = {'repeat': d[0], 'duration': d[1], 'offset1': d[2], 'offset2': d[3]}
		elif (header == 'z'):  # SDP 5.11 Time Zones z=<adjustment time> <offset> <adjustment time> <offset> .... Used for change in timezones such as day light savings time.
			d = data.split()
			amount = len(d) / 2
			self.body[header] = {}
			for x in range(int(amount)):
				self.body[header]['adjustment-time' + str(x)] = d[x * 2]
				self.body[header]['offset' + str(x)] = d[x * 2 + 1]
		elif (header == 'k'):  # SDP 5.12 Encryption Keys k=<method> k=<method>:<encryption key>
			if (':' in data):
				d = data.split(':')
				self.body[header] = {'method': d[0], 'key': d[1]}
			else:
				self.body[header] = {'method': d}
		elif (header == 'm'):  # SDP 5.14 Media Descriptions m=<media> <port>/<number of ports> <proto> <fmt> ... // exp: m=audio 18754 RTP/AVP 8 0 101
			d = data.split(' ')
			port = d[1]
			count = 1
			methods = d[3:]
			self.body['m'] = {'type': d[0], 'port': int(port), 'port_count': count, 'protocol': d[2], 'methods': methods}
		elif (header == 'a'):
			if ('a' not in self.body):
				self.body['a'] = []
			if (':' in data):
				d = data.split(':')
				attribute = d[0]
				value = d[1]
				if (attribute == 'rtpmap'):
					r = value.split(' ')
					b = r[1].split('/')
					if (b[0] == 'telephone-event'):
						if (int(r[0]) not in rtp_maps):
							rtp_maps[int(r[0])] = ['telephone-event', int(b[1]), 1]
			else:
				attribute = data
				value = None
			self.body['a'].append({'attribute': attribute, 'value': value})
		else:
			self.body[header] = data

class IPPhone:
	def __init__(self, username: str, domain: str, password: str, phone_ip: str, phone_port: int, rtp_port_low: int, rtp_port_high: int, proxy_address: str, proxy_port: int):
		self.username: str = username
		self.domain: str = domain
		self.password: str = password
		self.phone_ip: str = phone_ip
		self.phone_port: int = phone_port
		self.rtp_port_low: int = rtp_port_low
		self.rtp_port_high: int = rtp_port_high
		if (self.rtp_port_low > self.rtp_port_high):
			error('Error! "rtp_port_high" must be >= "rtp_port_low"')
		self.sip_send_address: str = proxy_address
		self.sip_send_port: int = proxy_port
		self.RTPCompatibleVersions = [2]
		self.rtp_prefered = [PCMU, EVENT]  # prefered codec, set to PCMU.
		self.rtp_local_ip: str = self.phone_ip
		self.rtp_local_port: int = self.rtp_port_low
		self.dtmf: str = ''
		self.rtp_active = False
		self.active = False
		self.state = common.PS_INACTIVE
		self.msg: SIPMessage = None
		self.register_counter = 0
		self.register_retry = 0
		self.register_timer = 0
		self.register_expires = 0
		self.reregister_timer = 0
		self.register_call_id = ''
		self.register_my_tag: str = ''
		self.register_other_tag: str = ''
		self.request_counter = 0
		self.response_timer = 0
		self.answer_timer = 0
		self.retry = 0
		self.call_id: str = ''
		self.line_cid: str = ''
		self.ip_cid: str = ''
		self.other_user: str = ''
		self.other_contact: str = ''
		self.branch: str = ''
		self.my_tag: str = ''
		self.other_tag: str = ''
		self.auth_cause = SS_UNKNOWN
		self.realm = None
		self.nonce = None
		self.opaque = None
		self.qop = None
		self.nonce_count: str = '0'
		self.cnonce = None
		self.uri = f'sip:{self.username}@{self.domain}'
		self.urn_uuid = uuid.uuid4()  # can be deleted when not using
		self.rinstance = self.gen_rinstance()  # can be deleted when not using

	def start(self) -> None:
		if (self.active):
			debug(f':ip_phone.start: Warning! IP Phone already started.')
			return
		self.active = True
		self.sip_sckt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sip_sckt.bind((self.phone_ip, self.phone_port))
		self.sip_sckt.setblocking(False)
		self.state = common.PS_REGISTERING
		self.register(common.REGISTER_EXPIRES)

	def stop(self) -> None:
		if (not self.active):
			debug(f':ip_phone.stop: Warning! IP Phone already stopped.')
			return
		if (self.call_id != ''):
			self.hangup()
		if (self.register_expires != 0):
			self.register(0)

	def inactivate(self) -> None:
		self.state = common.PS_INACTIVE
		self.register_expires = 0
		self.register_timer = 0
		self.reregister_timer = 0
		self.register_call_id = ''
		self.register_my_tag: str = ''
		self.register_other_tag: str = ''
		if (hasattr(self, 'sip_sckt')):
			if (self.sip_sckt):
				self.sip_sckt.close()
		self.active = False

	def register(self, exp = None) -> None:
		debug(f':ip_phone.register: exp: {exp}')
		if (self.register_call_id == ''):  # use same call_id and same tag for all messages
			self.register_call_id = self.gen_call_id()
		self.register_expires = exp
		self.register_retry = self.register_counter + 2
		self.register_timer = time.time() + common.RESPONSE_TIMEOUT
		self.sip_send(self.build_register_req())

	def call(self, line_cid: str, other_user: str) -> None:
		debug(f':ip_phone.call: line_cid: {line_cid:}, number: {other_user}')
		self.line_cid = line_cid
		self.other_contact = self.other_user = other_user
		self.call_id = self.gen_call_id()
		self.my_tag = self.gen_tag()
		self.state = common.PS_DIALING
		self.rtp_local_port = self.request_port()
		self.response_timer = time.time() + common.RESPONSE_TIMEOUT
		self.answer_timer = time.time() + common.ANSWER_TIMEOUT
		self.retry = self.request_counter + 2
		self.sip_send(self.build_req('INVITE'))

	def answer(self) -> None:
		debug(':ip_phone.answer: ...')
		self.create_rtp_clients()
		self.response_timer = time.time() + common.RESPONSE_TIMEOUT
		self.sip_send(self.build_resp(SS_OK))

	def hangup(self) -> None:
		if (self.state == common.PS_CONNECTED):
			self.state = common.PS_HANGINGUP
			self.response_timer = time.time() + common.RESPONSE_TIMEOUT
			self.sip_send(self.build_req('BYE'))
			debug(':ip_phone.hangup: Call state PS_CONNECTED changed to PS_HANGINGUP, BYE sent.')
		elif (self.state == common.PS_DIALING):
			self.state = common.PS_CANCELING
			self.response_timer = time.time() + common.RESPONSE_TIMEOUT
			self.sip_send(self.build_req('CANCEL'))
			debug(':ip_phone.hangup: Call state PS_DIALING changed to PS_CANCELING, CANCEL sent.')
		elif (self.state == common.PS_RINGING):
			self.delete_call()
			debug(':ip_phone.hangup: Call state PS_RINGING  changed to PS_IDLE, call deleted.')

	def delete_call(self) -> None:
		debug(f':ip_phone.delete_call: {self.call_id}')
		self.response_timer = 0
		self.answer_timer = 0
		self.retry = 0
		self.rtp_stop()
		self.state = common.PS_IDLE
		self.call_id = ''
		self.line_cid = ''
		self.ip_cid = ''

	def handler(self) -> None:
		msg = self.sip_receive()
		if (msg == None):  # handle timers
			if (self.register_timer != 0):  # registering
				if (time.time() > self.register_timer):
					self.register_timer = 0
					common.error(':ip_phone.handler: Error! Register timeout occured!')
					self.inactivate()  # may retry when installed in service mode according to service parameters
			if (self.response_timer != 0):
				if (time.time() > self.response_timer):  # not responded request, timed out
					debug(f':ip_phone.handler: Warning! Response timeout occured. call_id: {self.call_id}, call_state: {self.state}')
					self.response_timer = 0
					if (self.call_id != ''):
						self.hangup()
			if (self.answer_timer != 0):
				if (time.time() > self.answer_timer):  # initiated call could not completed, answer timed out
					debug(f':ip_phone.handler: Warning! Answer timeout occured. call_id: {self.call_id}, call_state: {self.state}')
					self.answer_timer = 0
					self.hangup()
			if (self.reregister_timer != 0):  # reregister
				if (time.time() > self.reregister_timer):
					self.reregister_timer = 0
					self.register(common.REGISTER_EXPIRES)
			return
		if (msg.version not in SIPCompatibleVersions):
			common.error(f':ip_phone.handler: Error! SIP Message Version {msg.version} not compatible:\r\n')
			return
		if (msg.msg_type == SIP_REQUEST):
			if (msg.method not in SIPCompatibleMethods):
				common.error(f':ip_phone.handler: Error! SIP Method {msg.method} not compatible:\r\n')
				return
		call_id = msg.headers['Call-ID']
		if (call_id == self.register_call_id):  # SIP REGISTER handling 
			self.register_timer = 0
			self.register_other_tag = msg.headers['To']['tag']
			if (msg.status == SS_OK):
				if (self.register_expires != 0):
					if (self.state == common.PS_REGISTERING):  # only when registering, do not change while reregistering
						self.state = common.PS_IDLE
					self.reregister_timer = time.time() + common.REGISTER_EXPIRES - 5
					debug(f':ip_phone.handler: IP Phone registered to {self.domain} as {self.username}.')
				else:
					debug(':ip_phone.handler: IP phone deregistered.')
					self.inactivate()
			elif (msg.status == SS_UNAUTHORIZED):   # Unauthorized, likely due to being password protected.
				if (self.register_counter < self.register_retry):
					self.auth_cause = msg.status
					self.realm = msg.authentication['realm']
					self.nonce = msg.authentication['nonce']
					if ('qop' in msg.authentication):
						self.qop = msg.authentication['qop']
					if ('opaque' in msg.authentication):
						self.opaque = msg.authentication['opaque']
					self.register_timer = time.time() + common.RESPONSE_TIMEOUT
					self.sip_send(self.build_register_req())
				else:  # At this point, it's reasonable to assume that this is caused by invalid credentials.
					common.error(f':ip_phone.handler: Error! Register unauthorized! Invalid credentials for {self.username}@{self.domain}')
					self.inactivate()
			elif (msg.status == SS_FORBIDDEN):
				common.error(f':ip_phone.handler: Error! Invalid credentials or SIP server address for {self.username}@{self.domain}')
				self.inactivate()
			elif (msg.status == SS_CALL_OR_TRANSACTION_DOESNT_EXIST):
				common.error(f':ip_phone.handler: Error! Invalid SIP message content. Received SIP Status 481: Call/Transaction Does Not Exist')
				self.inactivate()
			else:
				self.unhandled_SIP_message(':ip_phone.handler: REGISTER')
			return
		if (self.state == common.PS_INACTIVE):  # if not registered yet
			return
		self.msg = msg
		if (call_id == self.call_id):  # call already initiated
			self.response_timer = 0  # got a message
		if (msg.msg_type == SIP_REQUEST):
			if ('Contact' in msg.headers):
				first = msg.headers['Contact'].split('sip:')
				second = first[1].split('>')
				if (len(second) > 1):
					self.other_contact = second[0]
				else:
					self.other_contact = second
			if (msg.method == 'INVITE'):  # should be a re-INVITE (this code may not be working!)
				if (self.state == common.PS_IDLE):
					self.call_id = call_id
					self.my_tag = self.gen_tag()
					self.other_user = msg.headers['From']['address']
					self.other_tag = msg.headers['From']['tag']
					if (common.IP_PHONE_CID_IS_NUMBER):  # invitee's (this process) caller id is using as dial out number
						self.ip_cid = msg.headers['To']['cid']  # check invitee's caller ID is a number or not, clear if not
					self.rtp_local_port = self.request_port()
					self.state = common.PS_RINGING
					self.sip_send(self.build_resp(SS_RINGING))
				elif (self.state == common.PS_CONNECTED):  # call already connected
					if (call_id == self.call_id):  # call already initiated
						debug(':ip_phone.handler: Re-negotiation detected!')
						self.my_tag = msg.headers['To']['tag']
						self.other_user = msg.headers['From']['address']
						self.other_tag = msg.headers['From']['tag']
						self.create_rtp_clients()
						self.sip_send(self.build_resp(SS_OK))
					else:
						self.sip_send(self.build_resp(SS_BUSY_HERE))
			elif (msg.method == 'BYE'):  # Call terminated normally
				self.sip_send(self.build_resp(SS_OK))
				if ((self.state == common.PS_CONNECTED) and (call_id == self.call_id)):
					self.delete_call()
			elif (msg.method == 'CANCEL'):  # Call terminated before connected (this almost impossible because call will be answered in 10-20 ms)
				self.sip_send(self.build_resp(SS_OK))  # OK for CANCEL
				self.sip_send(self.build_resp(SS_REQUEST_TERMINATED))  # REQUEST_TERMINATED for INVITE
				if ((self.state == common.PS_RINGING) and (call_id == self.call_id)):
					self.state = common.PS_CANCELING
			elif (msg.method == 'ACK'):
				if (call_id == self.call_id):  # call already initiated
					if (self.state == common.PS_RINGING):
						debug(f':ip_phone.handler: Incoming call established. call_id: {self.call_id}')
						self.rtp_start()
						if (common.IP_PHONE_CID_IS_NUMBER):
							li = len(self.ip_cid)
							if (li > 0):
								self.dtmf = self.ip_cid
								i = 0
								while (i < li):
									if (self.ip_cid[i] not in common.DTMF_DIGITS):  # check all characters are DTMF digits (includig #*ABCD)
										self.dtmf = ''  # clear and exit if not
										break
									i += 1
						self.state = common.PS_CONNECTED
					elif (self.state == common.PS_CANCELING):
						self.delete_call()
			else:
				self.unhandled_SIP_message(':ip_phone.handler: SIP_REQUEST')
		else:  # SIP_RESPONSE
			if (call_id == self.call_id):  # call already initiated
				self.other_tag = msg.headers['To']['tag']
				if ('Contact' in msg.headers):
					first = msg.headers['Contact'].split('sip:')
					second = first[1].split('>')
					if (len(second) > 1):
						self.other_contact = second[0]
					else:
						self.other_contact = second
				if (msg.status == SS_OK):
					if (self.state == common.PS_DIALING):
						debug(':ip_phone.handler: Outgoing call established.')
						self.answer_timer = 0
						self.create_rtp_clients()
						self.sip_send(self.build_req('ACK_200'))
						self.rtp_start()
						self.state = common.PS_CONNECTED
					elif (self.state == common.PS_HANGINGUP):
						self.delete_call()
					elif (self.state == common.PS_CANCELING):
						self.response_timer = time.time() + common.RESPONSE_TIMEOUT
						self.state = common.PS_DELETING
					elif (self.state == common.PS_DELETING):  # needs to wait got two responses: SS_OK and SS_REQUEST_TERMINATED
						self.delete_call()
				elif ((msg.status == SS_UNAUTHORIZED) or (msg.status == SS_FORBIDDEN) or (msg.status == SS_PROXY_AUTHENTICATION_REQUIRED)):
					if (self.state == common.PS_DIALING):
						if (self.request_counter < self.retry):
							self.auth_cause = msg.status
							self.realm = msg.authentication['realm']
							self.nonce = msg.authentication['nonce']
							if ('qop' in msg.authentication):
								self.qop = msg.authentication['qop']
							if ('opaque' in msg.authentication):
								self.opaque = msg.authentication['opaque']
							if (msg.status == SS_PROXY_AUTHENTICATION_REQUIRED):
								self.sip_send(self.build_req('ACK'))
							self.response_timer = time.time() + common.RESPONSE_TIMEOUT
							self.sip_send(self.build_req('INVITE'))
						else:
							common.error(f':ip_phone.handler: Error! Call unauthorized! Invalid credentials for {self.username}@{self.domain}')
							self.delete_call()
				elif ((msg.status == SS_TRYING) or (msg.status == SS_PUSH_SENT) or (msg.status == SS_RINGING)):
					pass
				elif ((msg.status == SS_TEMPORARILY_UNAVAILABLE) or (msg.status == SS_BUSY_HERE) or (msg.status == SS_DECLINE)):
					self.sip_send(self.build_req('ACK'))
					self.delete_call()
				elif (msg.status == SS_REQUEST_TERMINATED):
					if (self.state == common.PS_CANCELING):
						self.response_timer = time.time() + common.RESPONSE_TIMEOUT
						self.state = common.PS_DELETING
						self.sip_send(self.build_req('ACK'))
					elif (self.state == common.PS_DELETING):  # needs to wait got two responses: SS_OK and SS_REQUEST_TERMINATED
						self.sip_send(self.build_req('ACK'))
						self.delete_call()
				elif (msg.status == SS_CALL_OR_TRANSACTION_DOESNT_EXIST):
					self.delete_call()
				elif (msg.status == SS_BAD_REQUEST):
					common.error(f':ip_phone.handler: Error! Received SIP BAD_REQUEST Message!')
					self.delete_call()
				elif (msg.status == SS_NOT_FOUND):
					common.error(f':ip_phone.handler: Error! IP Phone number not found!')
					self.delete_call()
				elif (msg.status == SS_SERVICE_UNAVAILABLE):  # not checking call_id, because may already be disconnected and deleted
					common.error(f':ip_phone.handler: Error! VoIP Service Unavailable!')
					self.delete_call()
				else:
					self.unhandled_SIP_message(':ip_phone.handler: SIP_RESPONSE')
			else:  # unknown call_id
				self.unhandled_SIP_message(':ip_phone.handler: SIP_RESPONSE -Unknown call-')

	def unhandled_SIP_message(self, source: str) -> None:
		debug(f'Warning! Unhandled SIP Message Received at {source}, Call State: {self.state}\r\n')
		pass

	def build_register_req(self) -> str:
		self.reg_branch = self.gen_branch()
		self.register_my_tag = self.gen_tag()
		self.register_other_tag = ''
		self.register_counter += 1
		req = f'REGISTER sip:{self.domain} SIP/2.0\r\n'
		req += f'Via: SIP/2.0/UDP {self.phone_ip}:{self.phone_port};branch={self.reg_branch}\r\n'
		req += f'From: <sip:{self.username}@{self.domain}>;tag={self.register_my_tag}\r\n'
		req += f'To: <sip:{self.username}@{self.domain}>'
		if (self.register_other_tag != ''):
			req += f';tag={self.register_other_tag}'
		req += f'\r\n'
		req += f'CSeq: {self.register_counter} REGISTER\r\n'
		req += f'Call-ID: {self.register_call_id}\r\n'
		req += 'Max-Forwards: 70\r\n'
		req += self.build_contact()
		req += f'Expires: {self.register_expires}\r\n'
		req += f'User-Agent: pstnxsip 1.0 v1.0\r\n'
		if (self.realm != None):
			req += f'Authorization: Digest realm="{self.realm}", nonce="{self.nonce}", algorithm=MD5, username="{self.username}", uri="{self.uri}", '
			if (self.qop != None):
				self.nonce_count = f'{(int(self.nonce_count, 16) + 1):0>8x}'
				self.cnonce = self.gen_cnonce()
				req += f'nc={self.nonce_count}, cnonce="{self.cnonce}", qop={self.qop}, '
			if (self.opaque != None):
				req += f'opaque="{self.opaque}", '
			req += f'response="{self.build_authorization_resp("REGISTER")}"\r\n'
		req += f'Allow: {(", ".join(SIPCompatibleMethods))}\r\n'
		req += 'Content-Length: 0\r\n\r\n'
		return req.encode('utf8')

	def build_req(self, req_type: str) -> str:  # ACK, CANCEL and BYE
		a = False
		if ((req_type == 'BYE') or (req_type == 'INVITE')):
			self.branch = self.gen_branch()
			self.request_counter += 1
		if (req_type == 'ACK_200'):
			req_type = 'ACK'
			a = True
		if (req_type == 'CANCEL'):
			self.other_tag = ''
		body = ''
		if (req_type == 'INVITE'):
			self.other_tag = ''
			body = self.build_sdp_body()
		b = len(body)
		req = f'{req_type} sip:{self.other_contact} SIP/2.0\r\n'
		req += f'Via: SIP/2.0/UDP {self.phone_ip}:{self.phone_port};branch='
		if (a):
			req += f'{self.gen_branch()}'
		else:
			req += f'{self.branch}'
		req += f'\r\n'
		if (self.msg != None):
			req += self.build_route()
			if ('Max-Forwards'in self.msg.headers):
				req += f'Max-Forwards: {self.msg.headers["Max-Forwards"]}\r\n'
			else:
				req += 'Max-Forwards: 70\r\n'
		else:
			req += 'Max-Forwards: 70\r\n'
		req += f'From: '
		if (self.line_cid != ''):
			req += f'"{self.line_cid}" '
		req += f'<sip:{self.username}@{self.domain}>;tag={self.my_tag}\r\n'
		req += f'To: <sip:{self.other_user}>'
		if (self.other_tag != ''):
			req += f';tag={self.other_tag}'
		req += f'\r\n'
		req += f'Call-ID: {self.call_id}\r\n'
		req += f'CSeq: {self.request_counter} {req_type}\r\n'
		if (req_type == 'INVITE'):
			req += self.build_contact()
			if (self.realm != None):
				if (self.auth_cause == SS_PROXY_AUTHENTICATION_REQUIRED):
					req += 'Proxy-'
				req += f'Authorization: Digest realm="{self.realm}", nonce="{self.nonce}", algorithm=MD5, username="{self.username}", uri="{self.uri}", '
				if (self.qop != None):
					self.nonce_count = f'{(int(self.nonce_count, 16) + 1):0>8x}'
					self.cnonce = self.gen_cnonce()
					req += f'nc={self.nonce_count}, cnonce="{self.cnonce}", qop={self.qop}, '
				if (self.opaque != None):
					req += f'opaque="{self.opaque}", '
				req += f'response="{self.build_authorization_resp("INVITE")}"\r\n'
			req += f'Allow: {(", ".join(SIPCompatibleMethods))}\r\n'
		if (b == 0):
			req += f'Content-Length: 0\r\n\r\n'
		else:
			req += 'Content-Type: application/sdp\r\n'
			req += f'Content-Length: {b}\r\n\r\n'
			req += body
		return req.encode('utf8')

	def build_resp(self, resp_code: int) -> str:  # can build response even call_id is different
		body = ''
		if ((resp_code == SS_OK) and (self.msg.headers["CSeq"]["method"] == 'INVITE')):
			body = self.build_sdp_body()
		b = len(body)
		resp = f'SIP/2.0 {resp_code} {sip_status[resp_code]}\r\n'
		resp += self.build_response_via_header()
		resp += self.build_record_route()
		if ('Max-Forwards'in self.msg.headers):
			resp += f'Max-Forwards: {self.msg.headers["Max-Forwards"]}\r\n'
		else:
			resp += 'Max-Forwards: 70\r\n'
		resp += f'From: {self.msg.headers["From"]["raw"]};tag={self.msg.headers["From"]["tag"]}\r\n'
		if ((resp_code == SS_OK) and (self.msg.headers["CSeq"]["method"] == 'INVITE')):
			resp += self.build_contact()
		resp += f'To: {self.msg.headers["To"]["raw"]}'
		if (self.msg.headers["Call-ID"] == self.call_id):
			resp += f';tag={self.my_tag}\r\n'
		else:
			resp += f';tag={self.msg.headers["To"]["tag"]}\r\n'
		resp += f'Call-ID: {self.msg.headers["Call-ID"]}\r\n'
		resp += f'CSeq: {self.msg.headers["CSeq"]["check"]} '
		if (resp_code == SS_REQUEST_TERMINATED):
			resp += f'INVITE\r\n'
		else:
			resp += f'{self.msg.headers["CSeq"]["method"]}\r\n'
		resp += f'Allow: {(", ".join(SIPCompatibleMethods))}\r\n'
		if (b == 0):
			resp += f'Content-Length: 0\r\n\r\n'
		else:
			resp += 'Content-Type: application/sdp\r\n'
			resp += f'Content-Length: {b}\r\n\r\n'
			resp += body
		return resp.encode('utf8')

	def build_response_via_header(self) -> str:
		via = ''
		for h_via in self.msg.headers['Via']:  # add Via headers
			v_line = f'Via: SIP/2.0/UDP {h_via["address"][0]}:{h_via["address"][1]}'
			if ('rport' in h_via.keys()):
				if (h_via['rport'] is not None):
					v_line += f';rport={h_via["rport"]}'
				else:
					v_line += ';rport'
			if ('received' in h_via.keys()):
				v_line += f';received={h_via["received"]}'
			if ('branch' in h_via.keys()):
				v_line += f';branch={h_via["branch"]}'
			v_line += '\r\n'
			via += v_line
		return via

	def build_record_route(self) -> str:
		rr = ''
		if ('Record-Route' in self.msg.headers):  # include Record-Routes
			for rr_line in self.msg.headers['Record-Route']:
				rr += f'Record-Route: {rr_line}\r\n'
		return rr

	def build_route(self) -> str:
		r = ''
		if ('Record-Route' in self.msg.headers):  # find Record-Routes
			for rr_line in self.msg.headers['Record-Route']:
				r = f'Route: {rr_line}\r\n' + r  # add in reverse order
		return r

	def build_contact(self) -> str:
		return 	f'Contact: <sip:{self.username}@{self.phone_ip}:{self.phone_port}>;+sip.instance="<urn:uuid:{self.urn_uuid}>"\r\n'

	"""
	f'Contact: <sip:{self.username}@{self.phone_ip}:{self.phone_port}>\r\n'
	f'Contact: <sip:{self.username}@{self.phone_ip}:{self.phone_port}>;rinstance={self.rinstance}\r\n'
	f'Contact: <sip:{self.username}@{self.phone_ip}:{self.phone_port}>;+sip.instance="<urn:uuid:{self.urn_uuid}>"\r\n'
	f'Contact: <sip:{self.username}@{self.phone_ip};gr=urn:uuid:{self.urn_uuid}>;+sip.instance="<urn:uuid:{self.urn_uuid}>"\r\n'
	"""

	def build_sdp_body(self) -> str:
		body = 'v=0\r\n'
		body += f'o=SIPxPSTN {str(random.randint(1, 100000))} {str(random.randint(1, 100000))} IN IP4 {self.phone_ip}\r\n'
		body += f's=SIPxPSTN\r\n'
		body += f'c=IN IP4 {self.phone_ip}\r\n'
		body += 't=0 0\r\n'
		body += f'm=audio {self.rtp_local_port} RTP/AVP'
		for c in self.rtp_prefered:
			body += f' {c}'
		body += '\r\n'
		for c in self.rtp_prefered:
			body += f'a=rtpmap:{c} {rtp_maps[c][0]}/{rtp_maps[c][1]}\r\n'
			if (c == EVENT):
				body += f'a=fmtp:{c} 0-15\r\n'
		body += 'a=maxptime:150\r\n'
		body += f'a=sendrecv\r\n'
		return body

	def gen_call_id(self) -> str:
		hash = hashlib.sha256(str(random.randint(1, 4294967296)).encode('utf8'))
		hhash = hash.hexdigest()
		return f'{hhash[0:32]}'

	def gen_tag(self) -> str:
		return hashlib.md5(str(random.randint(1, 4294967296)).encode('utf8')).hexdigest()[0:8]

	def gen_cnonce(self) -> str:
		return hashlib.md5(str(random.randint(1, 4294967296)).encode('utf8')).hexdigest()[0:32]

	def gen_rinstance(self) -> str:
		return hashlib.md5(str(random.randint(1, 4294967296)).encode('utf8')).hexdigest()[0:16]

	def gen_branch(self, length=32) -> str:
		branchid = uuid.uuid4().hex[: length - 7]
		return f'z9hG4bK{branchid}'

	def build_authorization_resp(self, method: str) -> bytes:
		HA1 = f'{self.username}:{self.realm}:{self.password}'.encode('utf8')
		HA1 = hashlib.md5(HA1).hexdigest()
		HA2 = f'{method}:{self.uri}'.encode('utf8')
		HA2 = hashlib.md5(HA2).hexdigest()
		if (self.qop == 'auth'):
			resp = f'{HA1}:{self.nonce}:{self.nonce_count}:{self.cnonce}:{self.qop}:{HA2}'.encode('utf8')
		else:
			resp = f'{HA1}:{self.nonce}:{HA2}'.encode('utf8')
		resp = hashlib.md5(resp).hexdigest()
		"""
		self.auth_cause = SS_UNKNOWN
		self.realm = None
		self.nonce = None
		self.opaque = None
		self.qop = None
		"""
		return resp

	def sip_receive(self) -> SIPMessage:
		msg = None
		raw = None
		if (not self.active):
			return None
		ready, _, _ = select.select([self.sip_sckt], [], [], 0)
		if (ready == []):
			return None
		raw, sender = self.sip_sckt.recvfrom(SIP_BUF_SIZE)
		if (raw != None):
			debug(f'\r\n:ip_phone.sip_recive: {sender[0]}:{sender[1]}\r\n{str(raw, "utf8")}')
			msg = SIPMessage(raw)
			if (msg.msg_type == None):
				common.error(f'\r\n:ip_phone.sip_recive: Error! Unable to decipher SIP request:\r\n')
				return None
		return msg

	def sip_send(self, msg: bytes) -> None:
		if (not self.active):
			debug(f':ip_phone.sip_send: Warning! IP Phone is not active.')
			return
		self.sip_sckt.sendto(msg, (self.sip_send_address, self.sip_send_port))
		debug(f'\r\n:ip_phone.sip_send: {self.sip_send_address}:{self.sip_send_port}\r\n{str(msg, "utf8")}')

	def request_port(self) -> int:
		return random.randint(self.rtp_port_low, self.rtp_port_high)

	def create_rtp_clients(self) -> None:
		codecs = {}
		for x in self.msg.body['m']['methods']:
			if (int(x) in self.rtp_prefered):
				codecs[x] = rtp_maps[int(x)]
				debug(f':ip_phone.create_rtp_clients: "{codecs[x]}" is compatible for RTP session.')
				break
		if (codecs == {}):
			common.error(f':ip_phone.create_rtp_clients: Error! No compatible codec found for call.')
			return
		self.rtp_remote_ip = self.msg.body['c']['address']
		self.rtp_remote_port = self.msg.body['m']['port']
		self.rtp_outSequence = random.randint(1, 100)
		self.rtp_outTimestamp = random.randint(1, 10000)
		self.rtp_outSSRC = random.randint(1000, 65530)

	def byte_to_bits(self, byte: bytes) -> str:
		nbyte = bin(ord(byte)).lstrip('-0b')
		nbyte = ('0' * (8 - len(nbyte))) + nbyte
		return nbyte

	def add_bytes(self, byte_string: bytes) -> int:
		binary = ''
		for byte in byte_string:
			nbyte = bin(byte).lstrip('-0b')
			nbyte = ('0' * (8 - len(nbyte))) + nbyte
			binary += nbyte
		return int(binary, 2)

	def rtp_start(self) -> None:
		if (self.rtp_active):
			self.rtp_stop()
		self.rtp_sckt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtp_sckt.bind((self.rtp_local_ip, self.rtp_local_port))
		self.rtp_sckt.setblocking(False)
		self.rtp_active = True

	def rtp_stop(self) -> None:
		if (self.rtp_active):
			self.dtmf = ''
			self.rtp_active = False
			if (hasattr(self, 'rtp_sckt')):
				if (self.rtp_sckt):
					self.rtp_sckt.close()

	def read_audio(self, length: int = RTP_PACKET_MAX_SIZE) -> bytes:  # RTP Receive
		data = None
		if (not self.rtp_active):  # if RTP is not active
			return data
		ready, _, _ = select.select([self.rtp_sckt], [], [], 0)
		if (ready == []):
			return data
		packet = self.rtp_sckt.recv(length)
		if (len(packet) != 0):  # parse RTP packet
			f_byte = self.byte_to_bits(packet[0:1])
			version = int(f_byte[0:2], 2)
			if (version not in self.RTPCompatibleVersions):
				debug(f':ip_phone.read_audio: Warning! RTP Version {version} not compatible.\r\nRTP Packet: {packet.hex()}')
				return data
			padding = bool(int(f_byte[2], 2))
			extension = bool(int(f_byte[3], 2))
			CC = int(f_byte[4:], 2)
			s_byte = self.byte_to_bits(packet[1:2])
			marker = bool(int(s_byte[0], 2))
			pt = int(s_byte[1:], 2)
			if (pt not in rtp_maps):
				debug(f':ip_phone.read_audio: Warning! RTP Payload type {pt} not found. Probably VoIP client application issue.\r\nRTP Packet: {packet.hex()}')
				return data
			sequence = self.add_bytes(packet[2:4])
			timestamp = self.add_bytes(packet[4:8])
			SSRC = self.add_bytes(packet[8:12])
			CSRC = []
			i = 12
			for x in range(CC):
				CSRC.append(packet[i : i + 4])
				i += 4
			payload = packet[i:]
			if (pt == PCMU):
				data = audioop.ulaw2lin(payload, 1)
				data = audioop.bias(data, 1, 128)
				return data
			elif (pt == PCMA):
				data = audioop.alaw2lin(payload, 1)
				data = audioop.bias(data, 1, 128)
				return data
			else:
				if (marker):
					key = common.DTMF_DIGITS
					self.dtmf += key[payload[0]]  # add last dialed key
					debug(f':ip_phone.read_audio: DTMF tone {self.dtmf} recieved from IP PBX.')
		return data

	def write_audio(self, payload: bytes) -> None:  #RTP Send
		if (not self.rtp_active):  # if RTP is not active
			return
		pl = len(payload)
		if (pl > RTP_PACKET_MAX_SIZE):
			return
		if (self.rtp_prefered[0] == PCMU):
			payload = audioop.bias(payload, 1, -128)
			payload = audioop.lin2ulaw(payload, 1)
		elif (self.rtp_prefered[0] == PCMA):
			payload = audioop.bias(payload, 1, -128)
			payload = audioop.lin2alaw(payload, 1)
		else:
			debug(f':ip_phone.write_audio: Warning! Unsupported codec (encode): {self.rtp_prefered[0]}')
			return
		packet = b'\x80'
		packet += chr(self.rtp_prefered[0]).encode('ascii')
		packet += self.rtp_outSequence.to_bytes(2, byteorder='big')
		packet += self.rtp_outTimestamp.to_bytes(4, byteorder='big')
		packet += self.rtp_outSSRC.to_bytes(4, byteorder='big')
		packet += payload
		if (self.rtp_outSequence == 0xFFFF):
			self.rtp_outSequence = 0
		else:
			self.rtp_outSequence += 1
		if (self.rtp_outTimestamp > (0xFFFFFFFF - pl)):
			self.rtp_outTimestamp = 0
		else:
			self.rtp_outTimestamp += pl
		self.rtp_sckt.sendto(packet, (self.rtp_remote_ip, self.rtp_remote_port))

	def read_dtmf(self) -> str:
		if (self.rtp_active):
			if (len(self.dtmf) > 0):
				dtmf = self.dtmf[0]
				self.dtmf = self.dtmf[1:]
				return dtmf
		return ''

	def send_dtmf(self, dtmf: str) -> None:
		if (not self.rtp_active):  # if RTP is not active
			return
		event = common.DTMF_DIGITS.find(dtmf)
		if (event == -1):  # not found
			return
		packet = b'\x80'
		packet += b'\xe5'  # set marker bit and dynamic payload (copied from asterisk)
		packet += self.rtp_outSequence.to_bytes(2, byteorder='big')
		packet += self.rtp_outTimestamp.to_bytes(4, byteorder='big')
		packet += self.rtp_outSSRC.to_bytes(4, byteorder='big')
		packet += bytes([event])  # pressed DTMF key
		packet += b'\x0a'  # E and Rbits, volume (copied from asterisk)
		packet += b'\x00'  # duration (copied from asterisk)
		packet += b'\xa0'  # duration (copied from asterisk)
		if (self.rtp_outSequence == 0xFFFF):
			self.rtp_outSequence = 0
		else:
			self.rtp_outSequence += 1
		if (self.rtp_outTimestamp == 0xFFFFFFFF):
			self.rtp_outTimestamp = 0
		else:
			self.rtp_outTimestamp += 1
		self.rtp_sckt.sendto(packet, (self.rtp_remote_ip, self.rtp_remote_port))
		debug(f':ip_phone.send_dtmf: DTMF {dtmf} sent to IP PBX.')
