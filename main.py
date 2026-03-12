from queue import Queue
from inFunction import receiver
import threading
import pigpio
import time

pi = pigpio.pi()

incoming_packets = Queue()
outgoing_packets = Queue()

BIT_RATE = 500
PACKET_BYTE_LENGTH = 8
GPIO_OUT = 17
GPIO_IN = 14
BIT_PERIOD = 1 / BIT_RATE


def receiver():
    while True:
        packet = receiver()  # your decoding logic
        if packet:
            incoming_packets.put(packet)
