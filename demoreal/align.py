import pigpio
import sys
import argparse

# Set up the argument parser
parser = argparse.ArgumentParser(description="Control GPIO 27 using pigpio.")
parser.add_argument('--stop', action='store_true', help="Turn GPIO 27 OFF instead of ON")
args = parser.parse_args()

# Define the GPIO pin (Broadcom/BCM numbering)
PIN = 27

# Connect to the local Raspberry Pi
pi = pigpio.pi()

# Check if we successfully connected to the daemon
if not pi.connected:
    print("Failed to connect to pigpiod. Did you run 'sudo pigpiod'?")
    sys.exit()

try:
    # Set the pin mode to OUTPUT
    pi.set_mode(PIN, pigpio.OUTPUT)

    if args.stop:
        # Write a 0 (LOW) to turn the GPIO pin OFF
        pi.write(PIN, 0)
        print(f"GPIO {PIN} is now OFF.")
    else:
        # Write a 1 (HIGH) to turn the GPIO pin ON
        pi.write(PIN, 1)
        print(f"GPIO {PIN} is now ON.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    # Close the connection to the daemon
    pi.stop()