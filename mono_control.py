from pyfirmata import Arduino, util
from time import sleep

board = Arduino("/dev/ttyAMA0")
lfo = board.get_pin("d:9:p")
pitch = board.get_pin("d:5:p")
cutoff = board.get_pin("d:6:p")

'''
while True:
  for i in range(3):
    pitch.write(0.0)
    sleep(0.2)
    pitch.write(1)
    sleep(0.2)
  for i in range(3):
    pitch.write(0.5)
    sleep(0.1)
    pitch.write(0.0)
    sleep(0.1)

while True:
  cutoff.write(0.0)
  sleep(0.1)
  cutoff.write(1.0)
  sleep(0.1)
'''