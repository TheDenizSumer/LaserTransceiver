import serial
import threading
import time

# Initialize Serial Port
# /dev/serial0 is the default primary UART on Raspberry Pi
ser = serial.Serial(
    port='/dev/serial0',
    baudrate=9600,      # Bits per second. Start at 9600, can go up to 115200+
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1           # Prevents the read function from hanging forever
)

def receiver_thread():
    print("[RX] Hardware Serial Listener Active...")
    while True:
        if ser.in_waiting > 0:
            # Read incoming bytes
            incoming_data = ser.read(ser.in_waiting).decode('utf-8', errors='replace')
            print(f"\n[Incoming]: {incoming_data}")
            print("> ", end="", flush=True)
        time.sleep(0.1)

def main():
    # Start the background listener
    rx_t = threading.Thread(target=receiver_thread, daemon=True)
    rx_t.start()

    print("--- Laser UART Terminal ---")
    print("Type message and hit Enter.")

    try:
        while True:
            msg = input("> ")
            if msg:
                # Send string over laser
                ser.write(msg.encode('utf-8'))
    except KeyboardInterrupt:
        print("\nClosing connection.")
        ser.close()

if __name__ == "__main__":
    main()