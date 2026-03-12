import RPi.GPIO as GPIO
import time



GPIO_PIN = 17          # Change to whatever GPIO you're using
BIT_RATE = 1000     # IN HERTZ
BIT_PERIOD = (1 / BIT_RATE) # in seconds
HALF_BIT = BIT_PERIOD / 2

GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIN, GPIO.OUT)

# Sending
def send_byte(byte):
    # Start bit
    GPIO.output(GPIO_PIN, GPIO.HIGH)
    time.sleep(BIT_PERIOD)

    # Data bits (LSB first)
    for i in range(8):
        bit = True if (byte >> i) & 1 else False
        print(bit)
        for x in range(2): # It takes two clock cycles for every bit for manchester encoding
            clock = True if x == 1 else False
            
            # Manchester Encoding
            outBit = clock ^ bit

            GPIO.output(GPIO_PIN, GPIO.HIGH if outBit else GPIO.LOW)
            time.sleep(BIT_PERIOD)

    # Stop bit
    GPIO.output(GPIO_PIN, GPIO.HIGH)
    time.sleep(BIT_PERIOD)

time.sleep(10)


send_byte(0b01100110)
time.sleep(3*BIT_PERIOD)
send_byte(0b01100100)
time.sleep(3*BIT_PERIOD)

print("sent")
GPIO.cleanup()


