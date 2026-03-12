import pigpio
import time
import threading
import queue

TX_PIN = 27
RX_PIN = 17

BIT_TIME = 0.002   # 2ms per bit = 500 baud
SAMPLE_OFFSET = BIT_TIME / 2

pi = pigpio.pi()

if not pi.connected:
    print("pigpio daemon not running")
    exit()

pi.set_mode(TX_PIN, pigpio.OUTPUT)
pi.set_mode(RX_PIN, pigpio.INPUT)

tx_queue = queue.Queue()


# -----------------------------
# TRANSMIT BYTE
# -----------------------------
def transmit_byte(byte):

    frame = []

    frame.append(1)  # start bit

    for i in range(8):
        frame.append((byte >> i) & 1)

    frame.append(0)  # stop bit

    for bit in frame:
        pi.write(TX_PIN, bit)
        time.sleep(BIT_TIME)


# -----------------------------
# TRANSMIT THREAD
# -----------------------------
def tx_loop():

    while True:

        msg = tx_queue.get()

        for c in msg:
            transmit_byte(ord(c))

        transmit_byte(ord("\n"))


# -----------------------------
# RECEIVE THREAD
# -----------------------------
def rx_loop():

    while True:

        # wait for start bit
        if pi.read(RX_PIN) == 1:

            time.sleep(SAMPLE_OFFSET)

            bits = []

            for i in range(8):
                time.sleep(BIT_TIME)
                bits.append(pi.read(RX_PIN))

            # stop bit
            time.sleep(BIT_TIME)

            value = 0
            for i,b in enumerate(bits):
                value |= (b << i)

            char = chr(value)

            print(char, end="", flush=True)

            # wait for line to drop
            while pi.read(RX_PIN) == 1:
                pass


# -----------------------------
# USER INPUT THREAD
# -----------------------------
def input_loop():

    while True:

        msg = input("TX> ")
        tx_queue.put(msg)


# -----------------------------
# START THREADS
# -----------------------------
threading.Thread(target=tx_loop, daemon=True).start()
threading.Thread(target=rx_loop, daemon=True).start()
threading.Thread(target=input_loop, daemon=True).start()


while True:
    time.sleep(1)