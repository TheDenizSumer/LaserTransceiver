import time
import threading
import pigpio

# --- CONFIGURATION ---
TX_PIN = 18        # GPIO pin connected to Laser
RX_PIN = 24        # GPIO pin connected to Photodiode
BIT_RATE = 500     # Bits per second (Start low for stability)
BIT_TIME = 1.0 / BIT_RATE
PREAMBLE = 0xAA    # 10101010
SYNC_WORD = 0x7E   # 01111110 (Start of Frame)

pi = pigpio.pi()
pi.set_mode(TX_PIN, pigpio.OUTPUT)
pi.set_mode(RX_PIN, pigpio.INPUT)

# --- TRANSMITTER LOGIC ---
def send_manchester_bit(bit):
    """Encodes a bit: 1 is Low->High, 0 is High->Low"""
    if bit == 1:
        pi.write(TX_PIN, 0)
        time.sleep(BIT_TIME / 2)
        pi.write(TX_PIN, 1)
        time.sleep(BIT_TIME / 2)
    else:
        pi.write(TX_PIN, 1)
        time.sleep(BIT_TIME / 2)
        pi.write(TX_PIN, 0)
        time.sleep(BIT_TIME / 2)

def transmit_packet(data_str):
    payload = data_str.encode('utf-8')
    checksum = sum(payload) % 256
    
    # Construct Frame: Preamble + Sync + Length + Payload + Checksum
    frame = [PREAMBLE, SYNC_WORD, len(payload)] + list(payload) + [checksum]
    
    print(f"\n[TX] Sending: {data_str}")
    for byte in frame:
        for i in range(7, -1, -1): # Send MSB first
            bit = (byte >> i) & 1
            send_manchester_bit(bit)
    pi.write(TX_PIN, 0) # Ensure laser is off after send

# --- RECEIVER LOGIC ---
def receiver_thread():
    print("[RX] Listener Started...")
    while True:
        # 1. Look for Preamble/Sync (Simplified for this example)
        # In a robust version, you'd use a rolling buffer to find SYNC_WORD
        if pi.read(RX_PIN) == 1: 
            # This is a placeholder for a more complex 'Start of Frame' detection
            # Real-world FSO requires edge-detection interrupts
            pass
        time.sleep(0.001)

# --- MAIN INTERACTION ---
def main():
    # Start the receiver in the background
    rx_t = threading.Thread(target=receiver_thread, daemon=True)
    rx_t.start()

    print("Laser Comm Terminal Active.")
    print("Type a message and press Enter to send.")
    
    try:
        while True:
            msg = input("> ")
            transmit_packet(msg)
    except KeyboardInterrupt:
        pi.write(TX_PIN, 0)
        pi.stop()

if __name__ == "__main__":
    main()