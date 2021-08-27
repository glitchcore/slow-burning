from math import ln
def read_temp(pin):
  R0 = 5.1e3
  B = 3435
  R25 = 10e3
  T_BASE = 25
  r2 = R0 * (1/pin.read() - 1.)
  k = log(r2 / R25) / B + 1.0 / (273.15 + T_BASE)
  return 1.0 / k - 273.15

from pyfirmata import Arduino, util
from time import sleep

board = Arduino("/dev/ttyAMA0")
lfo = board.get_pin("d:9:p")
pitch = board.get_pin("d:5:p")
cutoff = board.get_pin("d:6:p")

# TODO check iterator here
it = util.Iterator(board)  
it.start()

temperature = board.get_pin("a:0:i")
humidity = board.get_pin("a:1:i")

temp_avg = 60.
hum_avg = 1.
while True:
  temp_avg = temp_avg * (1. - 0.02) + read_temp(temperature) * 0.02
  hum_avg = hum_avg * (1. - 0.01) + 4.9 * board.analog[1].read() * 0.01
  print("hum: %0.2f" % hum_avg)
  print("temp: %0.2f" % temp_avg)
  sleep(0.1)

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