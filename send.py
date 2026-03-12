from queue import Queue
from outQueue import build_chunk
from readFile import read_bytes
import threading
import time
import os
import glob



def send():
    # takes 8 sets of 6 bytes
    payload = read_bytes(48)

    # set of 8 packets, each with 6 bytes of data, and header/parity bits added by build_chunk
    chunk = build_chunk(payload)

    print(chunk)

send()