import pigpio
import time
from main import BIT_RATE, PACKET_BYTE_LENGTH

RX_PIN = 24
BIT_TIME = 1.0 / BIT_RATE

HALF_BIT = BIT_TIME / 2
FRAME_BITS = PACKET_BYTE_LENGTH * 8
FRAME_GAP = 3 * BIT_TIME

pi = pigpio.pi()

last_tick = None
last_level = None

bit_buffer = []
frame_ready = False


def edge_callback(gpio, level, tick):

    global last_tick, last_level, bit_buffer, frame_ready

    if last_tick is None:
        last_tick = tick
        last_level = level
        return

    dt = pigpio.tickDiff(last_tick, tick)

    # Detect frame break
    if dt > FRAME_GAP:
        if len(bit_buffer) == FRAME_BITS:
            frame_ready = True
            print("Frame:", bit_buffer)
        bit_buffer = []

    else:

        # Manchester decode on full-bit transition
        if dt > HALF_BIT * 1.5:

            if last_level == 0 and level == 1:
                bit_buffer.append(1)

            elif last_level == 1 and level == 0:
                bit_buffer.append(0)

            if len(bit_buffer) > FRAME_BITS:
                bit_buffer = []

    last_tick = tick
    last_level = level


pi.set_mode(RX_PIN, pigpio.INPUT)

cb = pi.callback(RX_PIN, pigpio.EITHER_EDGE, edge_callback)

try:
    while True:

        if frame_ready:
            frame_ready = False

            # Convert bits to integer
            value = int("".join(map(str, bit_buffer)), 2)

            print("Decoded:", value)

            bit_buffer = []

except KeyboardInterrupt:
    pass

cb.cancel()
pi.stop()





