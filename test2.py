import pigpio
import time

GPIO_PIN = 27
bit_time = 1000 #mircoseconds
BIT_PERIOD = bit_time * 1/1000000 # convert to seconds
pi = pigpio.pi()

if not pi.connected:
    print("Could not connect to pigpiod!")
    exit()

pi.set_mode(GPIO_PIN, pigpio.OUTPUT)
pi.wave_clear()


# Create a simple 1-second-on, 1-second-off wave
flash1 = [
    pigpio.pulse(1 << GPIO_PIN, 0, 1000000),
    pigpio.pulse(0, 1 << GPIO_PIN, 1000000)
]

pi.wave_add_generic(flash1)

flash2 = [
    pigpio.pulse(1 << GPIO_PIN, 0, 500000),
    pigpio.pulse(0, 1 << GPIO_PIN, 1000000)
]

pi.wave_add_generic(flash2)

flash3 = [
    pigpio.pulse(1 << GPIO_PIN, 0, 500000),
    pigpio.pulse(0, 1 << GPIO_PIN, 200000)
]

pi.wave_add_generic(flash3)



wid = pi.wave_create()

if wid >= 0:
    print(f"Wave created with ID {wid}. Sending...")
    pi.wave_send_repeat(wid)
    time.sleep(10) # Let it blink for 10 seconds
    pi.wave_tx_stop()
    pi.wave_delete(wid)
else:
    print("Wave creation failed!")

pi.stop()