import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO_PIN = 17          # Change to whatever GPIO you're using
BIT_PERIOD = 0.200     # 200 ms (must match Arduino)
HALF_BIT = BIT_PERIOD / 2


# Sending
def send_byte(byte):
    # Start bit
    GPIO.output(GPIO_PIN, GPIO.LOW)
    time.sleep(BIT_PERIOD)

    # Data bits (LSB first)
    for i in range(8):
        bit = True if (byte >> i) & 1 else False

        for x in range(2): # It takes two clock cycles for every bit for manchester encoding
            clock = True if x == 1 else False
            
            # Manchester Encoding
            outBit = clock ^ bit

            GPIO.output(GPIO_PIN, GPIO.HIGH if outBit else GPIO.LOW)
            time.sleep(BIT_PERIOD)

    # Stop bit
    GPIO.output(GPIO_PIN, GPIO.HIGH)
    time.sleep(BIT_PERIOD)

