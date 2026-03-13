#!/usr/bin/env python3
"""
Raw RX monitor - run on the RECEIVING Pi to debug.
Prints GPIO 17 state every 50ms. When the other Pi transmits,
you should see the values change (0/1 toggling).

If you see no change: check alignment, wiring, or try RX_INVERTED=1.
"""

import os
import sys
import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO not found. Run on a Raspberry Pi.")
    sys.exit(1)

GPIO_RX = 17
SAMPLE_MS = 50

GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_RX, GPIO.IN)

print(f"Monitoring GPIO {GPIO_RX} (photodiode input) every {SAMPLE_MS}ms.")
print("Start transmitting from the other Pi - you should see 0/1 toggling.")
print("If stuck on one value: try RX_INVERTED=1, or check alignment/wiring.")
print("Ctrl+C to stop.\n")

try:
    while True:
        val = GPIO.input(GPIO_RX)
        ts = time.strftime("%H:%M:%S")
        bar = "█" if val else "░"
        print(f"\r[{ts}] GPIO17={val} {bar}  ", end="", flush=True)
        time.sleep(SAMPLE_MS / 1000.0)
except KeyboardInterrupt:
    print("\nDone.")
finally:
    GPIO.cleanup()
