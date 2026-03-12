import pigpio

pi = pigpio.pi()
import time

TX_PIN = 11
bit_time = 10e-6  # seconds

pi.set_mode(TX_PIN, pigpio.OUTPUT)

def send_bit(bit):
    if bit == 1:
        pi.write(TX_PIN, 0)
        time.sleep(bit_time/2)
        pi.write(TX_PIN, 1)
        time.sleep(bit_time/2)
    else:
        pi.write(TX_PIN, 1)
        time.sleep(bit_time/2)
        pi.write(TX_PIN, 0)
        time.sleep(bit_time/2)

def send_packet(bits):
    for b in bits:
        send_bit(b)

packet = [1,0,1,1,0,0,1]
send_packet(packet)