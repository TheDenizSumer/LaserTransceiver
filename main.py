from queue import Queue
from inFunction import receiver
import threading

import pigpio

incoming_packets = Queue()
outgoing_packets = Queue()

BIT_RATE = 500
PACKET_BYTE_LENGTH = 8


def receiver():
    while True:
        packet = receiver()  # your decoding logic
        if packet:
            incoming_packets.put(packet)
