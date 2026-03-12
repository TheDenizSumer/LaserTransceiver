import pigpio
import time

GPIO_PIN = 27 
pi = pigpio.pi()

if not pi.connected:
    print("Could not connect to pigpiod!")
    exit()

pi.set_mode(GPIO_PIN, pigpio.OUTPUT)

# Create a simple 1-second-on, 1-second-off wave
flash = [
    pigpio.pulse(1 << GPIO_PIN, 0, 1000000),
    pigpio.pulse(0, 1 << GPIO_PIN, 1000000)
]

pi.wave_clear()
pi.wave_add_generic(flash)
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