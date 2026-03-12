import RPi.GPIO as GPIO
import time

# ======================
# CONFIGURATION
# ======================

GPIO_PIN = 17          # Change to whatever GPIO you're using
BIT_PERIOD = 0.200     # 200 ms (must match Arduino)
HALF_BIT = BIT_PERIOD / 2

# ======================
# SETUP
# ======================

GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Listening for optical data...")

def read_byte():
    """
    Waits for a start bit and reads one byte (8 bits, LSB first)
    """

    # Wait for start bit (falling edge: HIGH -> LOW)
    while GPIO.input(GPIO_PIN) == GPIO.HIGH:
        pass

    # Move to middle of first data bit
    time.sleep(BIT_PERIOD + HALF_BIT)

    value = 0

    for i in range(8):
        bit = GPIO.input(GPIO_PIN)
        value |= (bit << i)  # LSB first
        time.sleep(BIT_PERIOD)

    # Optional: check stop bit
    stop_bit = GPIO.input(GPIO_PIN)
    if stop_bit != GPIO.HIGH:
        print("Warning: Stop bit error")

    return value


try:
    while True:
        byte = read_byte()
        print(chr(byte), end='', flush=True)

except KeyboardInterrupt:
    print("\nExiting...")
    GPIO.cleanup()
