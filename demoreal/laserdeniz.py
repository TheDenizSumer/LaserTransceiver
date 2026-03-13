import pigpio
import time
import threading

# Configuration
TX_PIN = 27
RX_PIN = 17
BAUD_RATE = 2000
BIT_TIME = 1.0 / BAUD_RATE

# Initialize pigpio
pi = pigpio.pi()
if not pi.connected:
    exit("Check if 'sudo pigpiod' is running!")

pi.set_mode(TX_PIN, pigpio.OUTPUT)
pi.set_mode(RX_PIN, pigpio.INPUT)
pi.set_pull_up_down(RX_PIN, pigpio.PUD_DOWN) # Assuming photoresistor pulls UP when hit

def send_byte(byte):
    """Sends 1 byte with a Start bit and Stop bit."""
    # 1. Preamble/Sync (Optional but helpful for the receiver to 'settle')
    # 2. Start Bit (High)
    pi.write(TX_PIN, 1)
    time.sleep(BIT_TIME)
    
    # 3. Data Bits (8 bits, LSB first)
    for i in range(8):
        bit = (byte >> i) & 1
        pi.write(TX_PIN, bit)
        time.sleep(BIT_TIME)
    
    # 4. Stop Bit (Low)
    pi.write(TX_PIN, 0)
    time.sleep(BIT_TIME)

def send_message(text):
    """Encodes string to bytes and sends via laser."""
    print(f"Sending: {text}")
    # Training sequence: 4 pulses of 1-0 to sync the receiver's eye
    for _ in range(4):
        pi.write(TX_PIN, 1); time.sleep(BIT_TIME)
        pi.write(TX_PIN, 0); time.sleep(BIT_TIME)
    
    for char in text:
        send_byte(ord(char))
    print("Done sending.")

def listener():
    """Continuously monitors RX_PIN for incoming data."""
    print("Receiver active. Listening...")
    while True:
        # Wait for a Start Bit (Transition from 0 to 1)
        if pi.read(RX_PIN) == 1:
            # Sync: Move to the middle of the Start Bit to sample reliably
            time.sleep(BIT_TIME * 1.5) 
            
            byte_val = 0
            for i in range(8):
                if pi.read(RX_PIN):
                    byte_val |= (1 << i)
                time.sleep(BIT_TIME)
            
            # Print character
            try:
                char = chr(byte_val)
                print(char, end='', flush=True)
            except:
                pass # Corrupt data
            
            # Wait for Stop Bit to finish
            time.sleep(BIT_TIME)
        else:
            time.sleep(BIT_TIME / 10) # Low-power idle

# Start the receiver thread
rx_thread = threading.Thread(target=listener, daemon=True)
rx_thread.start()

# Main Loop for User Input
try:
    print("--- Laser Transceiver Initialized ---")
    print(f"Baud Rate: {BAUD_RATE} | TX: {TX_PIN} | RX: {RX_PIN}")
    while True:
        msg = input("\nEnter message to send (or 'q' to quit): ")
        if msg.lower() == 'q':
            break
        send_message(msg)

except KeyboardInterrupt:
    pass
finally:
    pi.write(TX_PIN, 0)
    pi.stop()