import pigpio
import sys

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

    # Write a 1 (HIGH) to turn the GPIO pin ON
    pi.write(PIN, 1)
    
    print(f"GPIO {PIN} is now ON.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    # Close the connection to the daemon
    # Note: The pin will remain ON even after the script exits
    pi.stop()