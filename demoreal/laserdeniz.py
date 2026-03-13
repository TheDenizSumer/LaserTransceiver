import pigpio
import time
import threading
import sys

TX_PIN = 27
RX_PIN = 17

BIT_TIME = 0.02   # seconds per bit (~50 baud demo)

pi = pigpio.pi()

if not pi.connected:
    print("pigpio daemon not running")
    sys.exit()

pi.set_mode(TX_PIN, pigpio.OUTPUT)
pi.set_mode(RX_PIN, pigpio.INPUT)

pi.write(TX_PIN, 0)

############################################
# TRANSMITTER
############################################

def send_bit(bit):
    pi.write(TX_PIN, bit)
    time.sleep(BIT_TIME)

def send_byte(byte):

    # start bit
    send_bit(1)

    for i in range(8):
        send_bit((byte >> i) & 1)

    # stop bit
    send_bit(0)

def send_text(text):

    for c in text:
        send_byte(ord(c))

############################################
# RECEIVER
############################################

def read_bit():
    time.sleep(BIT_TIME)
    return pi.read(RX_PIN)

def receive_loop():

    while True:

        # wait for start bit
        while pi.read(RX_PIN) == 0:
            time.sleep(BIT_TIME / 4)

        # align to middle of first data bit
        time.sleep(BIT_TIME)

        byte = 0

        for i in range(8):
            bit = read_bit()
            byte |= (bit << i)

        # stop bit
        time.sleep(BIT_TIME)

        try:
            print(chr(byte), end='', flush=True)
        except:
            pass


############################################
# THREADS
############################################

def input_loop():

    while True:
        msg = input("\nSend: ")
        send_text(msg + "\n")


rx_thread = threading.Thread(target=receive_loop)
rx_thread.daemon = True
rx_thread.start()

input_loop()