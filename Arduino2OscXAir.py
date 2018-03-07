#!/usr/bin/python3
import serial
#import syslog
import sys
import time
import random
import socket
import errno
import os
import re
import asyncio
import math

from pythonosc import osc_message_builder
from pythonosc import udp_client
from multiprocessing import Process
from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import osc_packet

class _SerialPort:
	def __init__(self, name, bus):
		self.name = name
		self.bus = bus
		self.serialport = serial.Serial(name, 9600, timeout=5)
		self.serialport.flush()
		self.waitingForResponse = False
		self.currentFaderIndex = 0
		self.hasLCD = False
		self.volumeUp = 0
		self.volumeDown = 0
		
def runtests():
	testBuildSerialMessage()
	
def testBuildSerialMessage():
	faderGroupName = b'C'
	bus = 16
	busname = 'busje komt zo'
	xairfaderlevel = '0.2345'
	
	print(buildSerialMessage(bus, faderGroupName, busname, xairfaderlevel))
	
	s = "CH1"
	print (str(atonum(s)).zfill(2))
	s = "CH17"
	print (str(atonum(s)).zfill(2))
	s = "CH0.231"
	print (str(atonum(s)))

def atonum(s):	
	p = re.compile(r'[^\d-]*(-?[\d]+(\.[\d]*)?([eE][+-]?[\d]+)?)')
	m = p.match(s)
	if m:
		result = m.groups()[0]
		if "." in result or "e" in result or "E" in result:
			return float(result)
		else:
			return int(result)
	else:
		return 0;
	
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def buildSerialMessage(faderGroupIndex, faderGroupName, faderName, xairfaderlevel):
	
	mutable_bytes = bytearray(faderGroupName)

	if faderGroupName == b'C':
		# faderGroupIndex [1..16]
		if faderGroupIndex <= 9:
			mutable_bytes.extend(b'0')
			mutable_bytes.append(faderGroupIndex + ord('0'))
		else:
			mutable_bytes.extend(b'1')
			mutable_bytes.append((faderGroupIndex - 10) + ord('0'))	

	else: 
		mutable_bytes.append(faderGroupIndex + ord('0'))
	
	mutable_bytes.append(int(xairfaderlevel[2]) + ord('0'))
	mutable_bytes.append(int(xairfaderlevel[3]) + ord('0'))
	if faderName != '':
		mutable_bytes.extend(faderName.encode('ascii'))
	mutable_bytes.extend(b'\n')
	
	return mutable_bytes
	
def main():	
	global faderGroup
	faderGroup = 0
	
	runtests()
	
	print("Setup multicastclient")
	
	clientmulticast = None
	ipaddress = get_ip()
	print(ipaddress)

	#for val in ipaddresses:
	a,b,c,d = ipaddress.split(".")
	if a == "10":
		mcastip = ".".join([a, "255", "255", "255"])
	elif a == "172":
		mcastip = ".".join([a, b, "255", "255"])
	elif a == "192":
		mcastip = ".".join([a, b, c, "255"])
	else:
		mcastip = ""
	
	if mcastip != "":
		print(mcastip)
	
		clientmulticast = udp_client.SimpleUDPClient(mcastip, 10024, True)
		clientmulticast._sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
		clientmulticast.send_message("/xinfo")

		#print(clientmulticast._sock.getsockname())

		# Receive response
		print ("waiting to receive")
		clientmulticast._sock.settimeout(2)
		try:
			#print 'received raw data {0} from ip {1}'.format(data, clientmulticast._socket.getsockname())
			
			# extract server ip from /xinfo
			#/xinfo,,,,"Returns info of the X-Air (eg firmware #, etc)",
			xairaddress = receive_message_from_client(clientmulticast)[0]
			
			clientmulticast._sock.close()
			clientmulticast = None
			
			Doit(xairaddress, port)
			
		except socket.timeout:
			print("closing socket")
			clientmulticast._sock.close()
			clientmulticast = None

	sys.exit()
	
def Doit(xairaddress, port):
	global oscClient
	
	time.sleep(1)

	print("Setup oscClient: x-air ipaddress = %s" % xairaddress)
	
	oscClient = udp_client.SimpleUDPClient(xairaddress, 10024)
	oscClient._sock.settimeout(2)
	oscClient._sock.setblocking(1)
	
	# initialize bus and aux out
	for i in range(6):
		# set all bus -> LR to off
		# /bus/1/mix/lr,i,0-1,"OFF, ON","Mixbus LR assignment",
		oscMsg = "/bus/{}/mix/lr".format(str(i+1))
		oscClient.send_message(oscMsg, 0)
		
		# set all aux out tap to PRE+M (9)
		# /routing/aux/01/pos,i,0-10,"AIN, AIN+M, IN, IN+M, PREEQ, PREEQ+M, POSTEQ, POSTEQ+M, PRE, PRE+M, POST","Routing Aux [1..6] tap",	
		oscMsg = "/routing/aux/{}/pos".format(str(i+1).zfill(2))
		oscClient.send_message(oscMsg, 9)
		
		# set aux source to bus 1-6
		# /routing/aux/01/src,i,0-55,"Ch01-16, AuxL-R, Fx1L-Fx4R, Bus1-6, Send1-4, L, R, U1-18","Routing Aux [1..6] source",
		oscMsg = "/routing/aux/{}/src".format(str(i+1).zfill(2))
		oscClient.send_message(oscMsg, 26 + i)

	time.sleep(1)

	ports = []
	for i in range(6):

		portname = '/dev/ttyACM' + str(i)
		className = '/sys/class/tty/{}/device'.format('ttyACM' + str(i))

		if os.path.exists(className):
			
			ports.append(_SerialPort(portname, i + 1))
			device_path = os.path.realpath(className)
			subsystem = os.path.basename(os.path.realpath(os.path.join(device_path, 'subsystem')))
			print(device_path)
	
	while True:
		time.sleep(0.1)
		for serialport in ports:
			handleBus(serialport)
			
def fetchValueByOscMessage(msg):
		oscClient.send_message(msg)
		return receive_message()[0]	

def handleBus(serialport):
	bus = serialport.bus
	currentFaderIndex = serialport.currentFaderIndex
	
	if serialport.waitingForResponse == False:
		# Send message
		
		faderGroupName = b'A'
		faderGroupIndex = bus
		faderName = ""
		oscMsg = ""
		
		if currentFaderIndex == 0:
		
			#/bus/1/config/name,s,,,"Mixbus name",
			#oscClient.send_message("/bus/{}/config/name".format(str(bus)))
			##faderName = receive_message(oscClient)[0]
			if serialport.hasLCD:
				oscMsg = "/bus/{}/config/name".format(str(bus))
				faderName = fetchValueByOscMessage(oscMsg)
		
			# Mixbus fader level
			#/bus/1/mix/fader,f,0.0-1.0,"-oo - +10","Mixbus fader level",
			oscMsg = "/bus/{}/mix/fader".format(str(bus))
		
		elif currentFaderIndex < 17:
			faderGroupName = b'C'
			faderGroupIndex = currentFaderIndex
		
			#/ch/01/config/name,s,,,"Channel scribble strip name",
			oscMsg = "/ch/{}/config/name".format(str(faderGroupIndex).zfill(2))
			oscClient.send_message(oscMsg)
			faderName = receive_message()[0]

			# channel [01..16] mixbus sends level
			# /ch/01/mix/01/level,f,0.0-1.0,"-oo - +10","Channel mixbus sends level",
			oscMsg = "/ch/{}/mix/{}/level".format(str(faderGroupIndex).zfill(2), str(bus).zfill(2))

		elif currentFaderIndex == 17:
			faderGroupName = b'L'
			faderGroupIndex = 1
			
			#/rtn/aux/config/name,s,,,"Aux Return name",
			oscMsg = "/rtn/aux/config/name";
			oscClient.send_message(oscMsg)
			faderName = receive_message()[0]

			# Aux Return mixbus sends level
			# /rtn/aux/mix/01/level,f,0.0-1.0,"-oo - +10","Aux Return mixbus sends level",
			oscMsg = "/rtn/aux/mix/{}/level".format(str(bus).zfill(2))
		
		else:
			faderGroupName = b'F'
			faderGroupIndex = currentFaderIndex - 17
			
			#/rtn/1/config/name,s,,,"Fx Return [1..4] name",
			oscMsg = "/rtn/{}/config/name".format(str(faderGroupIndex))
			oscClient.send_message(oscMsg)
			faderName = receive_message()[0]

			# Fx Return [1..4] mixbus sends level
			# /rtn/1/mix/01/level,f,0.0-1.0,"-oo - +10","Fx Return [1..4] mixbus sends level",
			oscMsg = "/rtn/{}/mix/{}/level".format(str(faderGroupIndex), str(bus).zfill(2))
		
		oscClient.send_message(oscMsg)
		
		# Receive volume from X-Air
		volume = receive_message()[0]
		
		# process volume change
		if serialport.volumeUp != 0:
			volume += (serialport.volumeUp / 100)
			if (volume >= 1.00):
				volume = 0.99
			#/bus/1/mix/fader,f,0.0-1.0,"-oo - +10","Mixbus fader level",
			#oscMsg = "/bus/{}/mix/fader".format(str(bus))
			oscClient.send_message(oscMsg, volume)
			serialport.volumeUp = 0

		if serialport.volumeDown != 0:
			volume += (serialport.volumeDown / 100)
			if (volume < 0):
				volume = 0
			#/bus/1/mix/fader,f,0.0-1.0,"-oo - +10","Mixbus fader level",
			#oscMsg = "/bus/{}/mix/fader".format(str(bus))
			oscClient.send_message(oscMsg, volume)
			serialport.volumeDown = 0

		xairfaderlevel = '%.5f' % volume
		
		serial_message = buildSerialMessage(faderGroupIndex, faderGroupName, faderName, xairfaderlevel)
		serialport.serialport.write(bytes(serial_message))
		serialport.serialport.flush()
		serialport.waitingForResponse = True
	
	while serialport.serialport.in_waiting:
	
		msg = serialport.serialport.readline()
		#print(msg)
		
		startswithOK = msg[0] == ord('O') and msg[1] == ord('K')
		if startswithOK:
		   serialport.hasLCD = msg[2] == ord('1')

		startswithCH = msg[0] == ord('C') and msg[1] == ord('H')
		if startswithCH:
			serialport.currentFaderIndex = atonum(msg.decode("ascii"))

		volumeUp = msg[0] == ord('V') and msg[1] == ord('+')
		if volumeUp:
			serialport.volumeUp = atonum(msg.decode("ascii"))

		volumeDown = msg[0] == ord('V') and msg[1] == ord('-')
		if volumeDown:
			serialport.volumeDown = atonum(msg.decode("ascii"))
			
		serialport.waitingForResponse = False

def receive_message_from_client(localclient):
	data, server = localclient._sock.recvfrom(4096)
	packet = osc_packet.OscPacket(data)
	for timed_msg in packet.messages:
		now = time.time()
		#print ("message param[0] %s" % timed_msg.message.params[0])
		return timed_msg.message.params

def receive_message():
	return receive_message_from_client(oscClient)
	
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())	