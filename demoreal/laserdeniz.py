import pigpio
import time
import threading
import queue

TX_PIN = 27
RX_PIN = 17

BIT_TIME = 0.003   # 3 ms per bit (~333 baud)

pi = pigpio.pi()
if not pi.connected:
    print("pigpio daemon not running")
    exit()

pi.set_mode(TX_PIN, pigpio.OUTPUT)
pi.set_mode(RX_PIN, pigpio.INPUT)

tx_queue = queue.Queue()


# -------------------
# TRANSMIT
# -------------------
def transmit_byte(byte):

    frame = []

    frame.append(1)  # start bit

    for i in range(8):
        frame.append((byte >> i) & 1)

    frame.append(0)  # stop bit

    for bit in frame:
        pi.write(TX_PIN, bit)
        time.sleep(BIT_TIME)


def tx_loop():

    while True:
        msg = tx_queue.get()

        for c in msg:
            transmit_byte(ord(c))

        transmit_byte(ord("\n"))


# -------------------
# RECEIVE
# -------------------
def rx_loop():

    last_state = 0

    while True:

        state = pi.read(RX_PIN)

        # detect rising edge (start bit)
        if state == 1 and last_state == 0:

            # move to middle of first data bit
            time.sleep(BIT_TIME * 1.5)

            bits = []

            for _ in range(8):
                bits.append(pi.read(RX_PIN))
                time.sleep(BIT_TIME)

            # ignore stop bit
            time.sleep(BIT_TIME)

            value = 0
            for i,b in enumerate(bits):
                value |= (b << i)

            try:
                print(chr(value), end="", flush=True)
            except:
                pass

        last_state = state


# -------------------
# USER INPUT
# -------------------
def input_loop():

    while True:
        msg = input("TX> ")
        tx_queue.put(msg)


# -------------------
# START THREADS
# -------------------
threading.Thread(target=tx_loop, daemon=True).start()
threading.Thread(target=rx_loop, daemon=True).start()
threading.Thread(target=input_loop, daemon=True).start()

while True:
    time.sleep(1)