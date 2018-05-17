#!/usr/bin/python3
import sys
import time
import random
import socket
import errno
import os
import re
import asyncio
import math

import rtmidi.midiutil
from pythonosc import osc_message_builder
from pythonosc import udp_client
from multiprocessing import Process
from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import osc_packet

midiNoteOn = 144 #90
midiCC = 176 #B0
firstFaderPitchNumber = 224 #EO
lastFaderPitchNumber = 231 #E7

firstEncoderIndex = 16
lastEncoderIndex = 23

firstFaderGoupButtonNumber = 91
lastFaderGoupButtonNumber = 94
firstMuteButtonNumber = 16
lastMuteButtonNumber = 23
firstSelectButtonNumber = 24
lastSelectButtonNumber = 31

selectButtonIndex = 0

lineInGroupIndex = 2
fxSendGroupIndex = 3
busFadersGroupIndex = 4
	
def runtests():
	return
	
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
	
class MidiHandler(object): 
	def __init__(self, name): 
		self.name = name 
 
	def __call__(self, event, data=None):
		global faderGroup
		global selectButtonIndex
		global lineInGroupIndex
		global fxSendGroupIndex
		global busFadersGroupIndex
		print ("current fadergroup # : ", faderGroup)
		#print ("current oscClientMidiHandler: ", oscClientMidiHandler)
		#print ("current returnPort: ", returnPort)
		message, deltatime = event 
		#print (message)
		if message[0] >= firstFaderPitchNumber and message[0] <= lastFaderPitchNumber:
			faderIndex = message[0] - firstFaderPitchNumber + 1
			fadervalue = message[2] * 127 + message[1]
			fadervalue = fadervalue / 127 / 127
			if faderGroup == 0 or faderGroup == 1: # channel [1-8] or channel [9-16]
				faderIndex = faderIndex + (faderGroup * 8)
				#/ch/01/mix/fader,f,0.0-1.0,"-oo - +10","Channel fader level",
				oscMsg = "/ch/{}/mix/fader".format(str(faderIndex).zfill(2))
				
				# Send fader position to X-Air
				oscClientMidiHandler.send_message(oscMsg, fadervalue)

			if faderGroup == lineInGroupIndex: # line input [17-18], effect returns [1..4] and LR mix
				if faderIndex == 1:
					# /rtn/aux/mix/fader,f,0.0-1.0,"-oo - +10","Aux Return fader level",
					oscMsg = "/rtn/aux/mix/fader"

					# Send fader position to X-Air
					oscClientMidiHandler.send_message(oscMsg, fadervalue)

				if faderIndex >= 2 and faderIndex <= 5:
					# /dca/1/fader,f,0.0-1.0,"-oo - +10","DCA fader level",
					oscMsg = "/dca/{}/fader".format(str(faderIndex - 1))

					# /rtn/1/mix/fader,f,0.0-1.0,"-oo - +10","Fx Return [1..4] fader level",
					#oscMsg = "/rtn/{}/mix/fader".format(str(faderIndex - 1))

					# Send fader position to X-Air
					oscClientMidiHandler.send_message(oscMsg, fadervalue)

				if faderIndex == 8:
					handleMainFaderPosition(fadervalue)
				
			if faderGroup == busFadersGroupIndex: # 6 bus (routed to aux outputs) master faders and LR mix
				if faderIndex >= 1 and faderIndex <= 6:
					oscMsg = "/bus/{}/mix/fader".format(str(faderIndex))
					
					# Send fader position to X-Air
					oscClientMidiHandler.send_message(oscMsg, fadervalue)
					
				if faderIndex == 8:
					handleMainFaderPosition(fadervalue)

			if faderGroup == fxSendGroupIndex:
				if faderIndex >= 1 and faderIndex <= 4:
					#/fxsend/1/mix/fader,f,0.0-1.0,"-oo - +10","Fx send fader level",
					oscMsg = "/fxsend/{}/mix/fader".format(str(faderIndex))

					# Send fader position to X-Air
					oscClientMidiHandler.send_message(oscMsg, fadervalue)
					
				if faderIndex == 8:
					handleMainFaderPosition(fadervalue)
				
			#or
			#if faderGroup == 4: # 4  aux input [17-18], 4 DCA, 2 effect-return, LR volume
		
		if message[0] == midiCC:
			if selectButtonIndex == 0: # pan 
				channelIndex = message[1] - firstEncoderIndex + 1
				if faderGroup == 0 or faderGroup == 1: # channel [1-8] or channel [9-16]
					channelIndex = channelIndex + (faderGroup * 8)
					# /ch/01/mix/pan,f,0.0-1.0,"-100 - +100","Channel pan value",
					oscMsg = "/ch/{}/mix/pan".format(str(channelIndex).zfill(2))
					panvalue = fetchValueByOscMessageInMidiHandler(oscMsg)

					print (panvalue)
					
					if message[2] > 64:
						panvalue = panvalue - ((message[2] - 64) / 64)
					else:
						panvalue = panvalue + (message[2] / 64)

					if panvalue > 1:
						panvalue = 0.999
					if panvalue < 0:
						panvalue = 0
					print (oscMsg, panvalue)
						
					oscClientMidiHandler.send_message(oscMsg, panvalue)
						
		if message[0] == midiNoteOn:
			if message[1] >= firstFaderGoupButtonNumber and message[1] <= lastFaderGoupButtonNumber and message[2] == 127:
				toggledFaderGroup = message[1] - firstFaderGoupButtonNumber + 1
				
				if faderGroup == toggledFaderGroup:
					faderGroup = 0
					message[2] = 0
					returnPort.send_message(message)	
				else:
					returnPort.send_message(message)	

					if faderGroup > 0:
						message[1] = firstFaderGoupButtonNumber + faderGroup - 1
						message[2] = 0
						returnPort.send_message(message)

					faderGroup = toggledFaderGroup

			if message[1] >= firstSelectButtonNumber and message[1] <= lastSelectButtonNumber and message[2] == 127:
				buttonIndex = message[1] - firstSelectButtonNumber + 1

				if selectButtonIndex == buttonIndex:
					# clear selected button
					selectButtonIndex = 0
					message[2] = 0
					returnPort.send_message(message)	
				else:
					# set new selected button 
					returnPort.send_message(message)	
					
					if selectButtonIndex > 0:
						# clear current selected button
						message[1] = firstSelectButtonNumber + selectButtonIndex - 1
						message[2] = 0
						returnPort.send_message(message)
						
					selectButtonIndex = buttonIndex
					
			if message[1] >= firstMuteButtonNumber and message[1] <= lastMuteButtonNumber and message[2] == 127:
				channelMuteIndex = message[1] - firstMuteButtonNumber + 1

				if faderGroup == 0 or faderGroup == 1: # channel [1-8] or channel [9-16]
					channelMuteIndex = channelMuteIndex + (faderGroup * 8)
					# /ch/01/mix/on,i,0-1,"OFF, ON","Channel mute",
					oscMsg = "/ch/{}/mix/on".format(str(channelMuteIndex).zfill(2))

					# Receive mute on/off from X-Air
					mute = fetchValueByOscMessageInMidiHandler(oscMsg)
					# Send channel mute on/off to X-Air
					oscClientMidiHandler.send_message(oscMsg, 1 - mute)
		
				if faderGroup == lineInGroupIndex: # line input [17-18], effect returns [1..4] and LR mix
					mute = 0
					if channelMuteIndex == 1:
						# /rtn/aux/mix/on,i,0-1,"OFF, ON","Aux Return mute",
						oscMsg = "/rtn/aux/mix/on"
						
						# Receive mute on/off from X-Air
						mute = fetchValueByOscMessageInMidiHandler(oscMsg)
						# Send mute on/off to X-Air
						oscClientMidiHandler.send_message(oscMsg, (1 - mute))
						
					if channelMuteIndex >= 2 and channelMuteIndex <= 5:
						# /dca/1/on,i,0-1,"OFF, ON","DCA [1..4] Off/On",
						oscMsg = "/dca/{}/on".format(str(channelMuteIndex - 1))

						# /rtn/1/mix/on,i,0-1,"OFF, ON","Fx Return [1..4] mute",
						#oscMsg = "/rtn/{}/mix/on".format(str(channelMuteIndex - 1))

						# Receive mute on/off from X-Air
						mute = fetchValueByOscMessageInMidiHandler(oscMsg)
						# Send mute on/off to X-Air
						oscClientMidiHandler.send_message(oscMsg, (1 - mute))
					
					if channelMuteIndex == 8:
						toggleMainMuteButton()
						
				if faderGroup == busFadersGroupIndex: # 6 bus (routed to aux outputs) master faders and LR mix
					if channelMuteIndex >= 1 and channelMuteIndex <= 6:
						# /bus/1/mix/on,i,0-1,"OFF, ON","Mixbus mute",
						oscMsg = "/bus/{}/mix/on".format(str(channelMuteIndex))

						# Receive mute on/off from X-Air
						mute = fetchValueByOscMessageInMidiHandler(oscMsg)
						# Send mute on/off to X-Air
						oscClientMidiHandler.send_message(oscMsg, (1 - mute))

					if channelMuteIndex == 8:
						toggleMainMuteButton()
						
				if faderGroup == fxSendGroupIndex:
					if channelMuteIndex >= 1 and channelMuteIndex <= 4:
						# /fxsend/1/mix/on,i,0-1,"OFF, ON","Fx send mute",
						oscMsg = "/fxsend/{}/mix/on".format(str(channelMuteIndex))
						
						# Receive mute on/off from X-Air
						mute = fetchValueByOscMessageInMidiHandler(oscMsg)
						# Send mute on/off to X-Air
						oscClientMidiHandler.send_message(oscMsg, (1 - mute))
						
					if channelMuteIndex == 8:
						toggleMainMuteButton()
		
def handleMainFaderPosition(fadervalue):
	# /lr/mix/fader,f,0.0-1.0,"-oo - +10","Main LR fader level",
	oscMsg = "/lr/mix/fader"

	# Send fader position to X-Air
	oscClientMidiHandler.send_message(oscMsg, fadervalue)

def toggleMainMuteButton():
	# /lr/mix/on,i,0-1,"OFF, ON","Main LR mute",
	oscMsg = "/lr/mix/on"
	
	# Receive mute on/off from X-Air
	mute = fetchValueByOscMessageInMidiHandler(oscMsg)
	# Send mute on/off to X-Air
	oscClientMidiHandler.send_message(oscMsg, (1 - mute))
						
def setupMidi():
	global returnPort
	try:
		midiin = rtmidi.MidiIn()
		names = midiin.get_ports()
		print (names)
		for name in names:
			print (name)
			port, port_name = rtmidi.midiutil.open_midiport(name)
			print (port)
			print (port_name)
			
			if "BCF2000" in name:
				print ("BCF Found!!")
				port.set_callback(MidiHandler(name))
				
				returnPort, port_name = rtmidi.midiutil.open_midiport(name, "output")
				print (returnPort)
				print (port_name)
				
				resetMidiController()
					
				return port
	except Exception as err:
		print ("exception in setupMidi: ", err)
			
def resetMidiController():
	# reset all faders
	for faderIndex in range(8):
		setControllerFaderPosition(faderIndex, 0)
		
	# reset fadergroup select buttons
	for buttonIndex in range(4):
		setControllerButton(firstFaderGoupButtonNumber + buttonIndex, 0)
		
	# reset channel mute buttons
	for faderIndex in range(8):
		setControllerMuteButton(faderIndex, 0)

	# reset channel select buttons
	for faderIndex in range(8):
		setControllerSelectButton(faderIndex, 0)	
	#

	
def main():	
	global faderGroup
	faderGroup = 0
	
	runtests()
	
	port = setupMidi()
	
	print("Setup multicastclient")
	
	clientmulticast = None
	ipaddress = get_ip()
	print(ipaddress)
	if ipaddress == "127.0.0.1":
		time.sleep(10)
		ipaddress = get_ip()
		print(ipaddress)
		
	#for val in ipaddresses:
	a,b,c,d = ipaddress.split(".")
	if a == "10":
		mcastip = ".".join([a, b, c, "255"])
	elif a == "172":
		mcastip = ".".join([a, b, c, "255"])
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
	global oscClientMidiHandler
	
	time.sleep(1)

	print("Setup oscClient: x-air ipaddress = %s" % xairaddress)
	
	oscClient = udp_client.SimpleUDPClient(xairaddress, 10024)
	oscClient._sock.settimeout(2)
	oscClient._sock.setblocking(1)
	
	oscClientMidiHandler = udp_client.SimpleUDPClient(xairaddress, 10024)
	oscClientMidiHandler._sock.settimeout(2)
	oscClientMidiHandler._sock.setblocking(1)	
	
	# initialize bus and aux out
	for i in range(6):
		# set all bus -> LR to off
		# /bus/1/mix/lr,i,0-1,"OFF, ON","Mixbus LR assignment",
		oscMsg = "/bus/{}/mix/lr".format(str(i+1))
		oscClient.send_message(oscMsg, 0)
		
		# set all aux out tap to POST (10)
		# /routing/aux/01/pos,i,0-10,"AIN, AIN+M, IN, IN+M, PREEQ, PREEQ+M, POSTEQ, POSTEQ+M, PRE, PRE+M, POST","Routing Aux [1..6] tap",	
		oscMsg = "/routing/aux/{}/pos".format(str(i+1).zfill(2))
		oscClient.send_message(oscMsg, 10)
		
		# set aux source to bus 1-6
		# /routing/aux/01/src,i,0-55,"Ch01-16, AuxL-R, Fx1L-Fx4R, Bus1-6, Send1-4, L, R, U1-18","Routing Aux [1..6] source",
		oscMsg = "/routing/aux/{}/src".format(str(i+1).zfill(2))
		oscClient.send_message(oscMsg, 26 + i)
	
	# initialize fx return
	for i in range(4):
		# set fader to main at 0 db (??f)
		# /rtn/1/mix/fader,f,0.0-1.0,"-oo - +10","Fx Return [1..4] fader level",
		oscMsg = "/rtn/{}/mix/fader".format(str(i+1))
		#oscClient.send_message(oscMsg, 0.7)

		# set send to LR on
		# /rtn/1/mix/lr,i,0-1,"OFF, ON","Fx Return [1..4] LR assignment",
		oscMsg = "/rtn/{}/mix/lr".format(str(i+1))
		#oscClient.send_message(oscMsg, 1)
		
		# set effect tap for the busses to pre 
		for j in range(6):
			# /rtn/1/mix/01/tap,i,0-5,"IN, PREEQ, POSTEQ, PRE, POST, GRP","Fx Return [1..4] mixbus sends tap",
			oscMsg = "/rtn/{}/mix/{}/tap".format(str(i+1), str(j+1).zfill(2))
			#oscClient.send_message(oscMsg, 3)
			
			# /rtn/1/mix/01/level,f,0.0-1.0,"-oo - +10","Fx Return [1..4] mixbus sends level",
			oscMsg = "/rtn/{}/mix/{}/level".format(str(i+1), str(j+1).zfill	(2))
			#oscClient.send_message(oscMsg, 0.0)

	time.sleep(1)
	
	print (port)		
	print (returnPort)

	while True:
		try:
			time.sleep(0.3)
			setMidiController()
		except Exception as err:
			print ("exception in loop: ", err)
			
def fetchValueByOscMessage(msg):
		oscClient.send_message(msg)
		return receive_message()[0]	
			
def fetchValueByOscMessageInMidiHandler(msg):
		oscClientMidiHandler.send_message(msg)
		return receive_message_from_client(oscClientMidiHandler)[0]	
		
def setMidiController():
	global faderGroup
	global busFaderGroupIndex
	global lineInGroupIndex
	global fxSendGroupIndex
	global busFadersGroupIndex
	
	print ("setMidiController faderGroup=", faderGroup)
	#print (selectButtonIndex)
	faderGroupLocal = faderGroup
	
	if faderGroup == 0 or faderGroup == 1: # channel [1-8] or channel [9-16]
		for faderIndex in range(8):
			if faderGroup != faderGroupLocal:
				break
			channelindex = (faderGroup * 8) + faderIndex + 1
			#/ch/01/mix/fader,f,0.0-1.0,"-oo - +10","Channel fader level",
			oscMsg = "/ch/{}/mix/fader".format(str(channelindex).zfill(2))

			# Receive fader position from X-Air
			faderposition = fetchValueByOscMessage(oscMsg)
			
			setControllerFaderPosition(faderIndex, faderposition)
			
			# getMuteButtonStatus
			# /ch/01/mix/on,i,0-1,"OFF, ON","Channel mute",
			oscMsg = "/ch/{}/mix/on".format(str(channelindex).zfill(2))

			mute = fetchValueByOscMessage(oscMsg)

			setControllerMuteButton(faderIndex, mute)
			
			if selectButtonIndex == 0:
				# if ... == 0: fetch gain and set rotary encoders.
				# 
				# if ... == 1: fetch pan and set rotary encoders.
				
				# /ch/01/mix/pan,f,0.0-1.0,"-100 - +100","Channel pan value",
				oscMsg = "/ch/{}/mix/pan".format(str(channelindex).zfill(2))
				#panvalue = fetchValueByOscMessage(oscMsg)

				#setControllerEncoder(faderIndex, panvalue)
			else:
				# encoder 1: /ch/01/preamp/hpf,f,0.0-1.0,"20 - 200","Channel low cut frequency (hz)",
				oscMsg = "/ch/{}/preamp/hpf".format(str(selectButtonIndex).zfill(2))
				#hpfvalue = fetchValueByOscMessage(oscMsg)
				#setControllerEncoder(selectButtonIndex - 1, panvalue)
				# encoder 1 button: /ch/01/preamp/hpf/on
				
	if faderGroup == lineInGroupIndex: # line input [17-18], effect returns [1..4]
		# /rtn/aux/mix/fader,f,0.0-1.0,"-oo - +10","Aux Return fader level",
		oscMsg = "/rtn/aux/mix/fader"
		# Receive fader position from X-Air
		faderposition = fetchValueByOscMessage(oscMsg)
		setControllerFaderPosition(0, faderposition)

		#/rtn/aux/mix/on,i,0-1,"OFF, ON","Aux Return mute",
		oscMsg = "/rtn/aux/mix/on"
		mute = fetchValueByOscMessage(oscMsg)
		setControllerMuteButton(0, mute)
		
		for faderIndex in range(4):
			# Fx Return [1..4]
			returnindex = faderIndex + 1
			# /dca/1/fader,f,0.0-1.0,"-oo - +10","DCA fader level",
			#oscMsg = "/dca/{}/fader".format(str(returnindex))

			# /rtn/1/mix/fader,f,0.0-1.0,"-oo - +10","Fx Return [1..4] fader level",
			oscMsg = "/rtn/{}/mix/fader".format(str(returnindex))
			# Receive fader position from X-Air
			faderposition = fetchValueByOscMessage(oscMsg)
			setControllerFaderPosition(returnindex, faderposition)
			
			# /dca/1/on,i,0-1,"OFF, ON","DCA [1..4] Off/On",
			#oscMsg = "/dca/{}/on".format(str(returnindex))

			#/rtn/1/mix/on,i,0-1,"OFF, ON","Fx Return [1..4] mute",
			oscMsg = "/rtn/{}/mix/on".format(str(returnindex))
			mute = fetchValueByOscMessage(oscMsg)
			setControllerMuteButton(returnindex, mute)
			
		# set 2 unused faders to 0
		setControllerFaderPosition(5, 0)
		setControllerFaderPosition(6, 0)
		
		setMainVolumeFader(7)

	if faderGroup == busFadersGroupIndex:
		for faderIndex in range(6):
			busindex = faderIndex + 1
			oscMsg = "/bus/{}/mix/fader".format(str(busindex))
			# Receive fader position from X-Air
			faderposition = fetchValueByOscMessage(oscMsg)
			setControllerFaderPosition(faderIndex, faderposition)
			
			# /bus/1/mix/on,i,0-1,"OFF, ON","Mixbus mute",
			oscMsg = "/bus/{}/mix/on".format(str(busindex))
			mute = fetchValueByOscMessage(oscMsg)
			setControllerMuteButton(faderIndex, mute)
			
		# set unused fader to 0
		setControllerFaderPosition(6, 0)

		setMainVolumeFader(7)
		
	if faderGroup == fxSendGroupIndex: # 4 fxsend and LR mix
		for faderIndex in range(4):
			sendIndex = faderIndex + 1
			# /fxsend/1/mix/fader,f,0.0-1.0,"-oo - +10","Fx send fader level",
			oscMsg = "/fxsend/{}/mix/fader".format(str(sendIndex))
			# Receive fader position from X-Air
			faderposition = fetchValueByOscMessage(oscMsg)
			setControllerFaderPosition(faderIndex, faderposition)

			# /fxsend/1/mix/on,i,0-1,"OFF, ON","Fx send mute",
			oscMsg = "/fxsend/{}/mix/on".format(str(sendIndex))
			mute = fetchValueByOscMessage(oscMsg)
			setControllerMuteButton(faderIndex, mute)
		
		# set 3 unused faders to 0
		setControllerFaderPosition(4, 0)
		setControllerFaderPosition(5, 0)
		setControllerFaderPosition(6, 0)

		setMainVolumeFader(7)
		
def setMainVolumeFader(faderIndex):
	# /lr/mix/fader,f,0.0-1.0,"-oo - +10","Main LR fader level",
	oscMsg = "/lr/mix/fader"
	# Receive fader position from X-Air
	faderposition = fetchValueByOscMessage(oscMsg)
	setControllerFaderPosition(faderIndex, faderposition)
	
	# /lr/mix/on,i,0-1,"OFF, ON","Main LR mute",
	oscMsg = "/lr/mix/on"
	mute = fetchValueByOscMessage(oscMsg)
	setControllerMuteButton(faderIndex, mute)
		
def setControllerButton(button, value):
	midi_message = bytearray(3)
	midi_message[0] = midiNoteOn
	midi_message[1] = button
	midi_message[2] = value
	
	returnPort.send_message(midi_message)
	
def setControllerMuteButton(index, value):
	button = index + firstMuteButtonNumber
	midi_message = bytearray(3)
	midi_message[0] = midiNoteOn
	midi_message[1] = button
	midi_message[2] = 127 * (1 - value)
	
	returnPort.send_message(midi_message)
	
def setControllerSelectButton(index, value):
	button = index + firstSelectButtonNumber
	midi_message = bytearray(3)
	midi_message[0] = midiNoteOn
	midi_message[1] = button
	midi_message[2] = 127 * value
	
	returnPort.send_message(midi_message)
	
def setControllerFaderPosition(index, faderposition):
	a = int(faderposition * 127 * 127)
	b = int(a / 127)
	c = a - (int(b) * 127)
	
	#
	midi_message = bytearray(3)
	midi_message[0] = firstFaderPitchNumber + index # pw channel 1
	midi_message[1] = c	# value lsb
	midi_message[2] = b # value msb
	
	returnPort.send_message(midi_message)
	
def setControllerEncoder(index, panvalue):
	# index = 0-7
	# panvalue = f,0.0-1.0
	encoder = firstEncoderIndex + index + 8
	midi_message = bytearray(3)
	midi_message[0] = midiCC + 2
	midi_message[1] = encoder
	midi_message[2] = 0 #int(panvalue * 127) #
		
	returnPort.send_message(midi_message)
	
def receive_message_from_client(localclient):

	data, server = localclient._sock.recvfrom(4096)
	packet = osc_packet.OscPacket(data)

	for timed_msg in packet.messages:
		now = time.time()
		return timed_msg.message.params

def receive_message():
	return receive_message_from_client(oscClient)
	
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())	