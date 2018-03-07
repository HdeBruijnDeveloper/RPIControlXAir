Script to control the mixer with a Behringer BCF2000 controller 



What is implemented in the first version:
8 faders with bank switching.
  bank 0: channel 1-8
  bank 1: channel 9-16
  bank 2: Aux in + Effect returns 1-4
  bank 3: Bus 1-6
  bank 4: Effect send 1-4 and Main LR
mute buttons (row beneath the rotery encoders)
select buttons (row above the faders no functionality yet)
panning (rotary encoders)

What is not working: LED ring around the encoders should be updated with the pan value.

What's next:
  Implement select buttons (each encoder will have their own function, like hpf frequency, gate threshold etc....)

Hardware setup:
A Behringer BCF2000 connected by USB to RPI. 
RPI connected by ethernet to te Behringer X-Air XR18 digital rackmixer.

Software:
Used libraries:
pyhton-osc
python-rtmidi

Files:
Python 3 script
