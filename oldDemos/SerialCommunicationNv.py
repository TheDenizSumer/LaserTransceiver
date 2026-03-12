import serial
import threading
import time

# --- JETSON NANO CONFIG ---
# UART 2 on the Header (Pins 8 & 10) is usually /dev/ttyTHS1
JETSON_UART = '/dev/ttyTHS1' 

ser = serial.Serial(
    port=JETSON_UART,
    baudrate=9600,
    timeout=1
)

def receiver_thread():
    print(f"[RX] Jetson Hardware Listener Active on {JETSON_UART}...")
    while True:
        if ser.in_waiting > 0:
            try:
                # Read and decode
                incoming = ser.read(ser.in_waiting).decode('utf-8', errors='replace')
                print(f"\n[Received]: {incoming}")
                print("> ", end="", flush=True)
            except Exception as e:
                print(f"Error reading: {e}")
        time.sleep(0.01) # Faster polling for Jetson

def main():
    rx_t = threading.Thread(target=receiver_thread, daemon=True)
    rx_t.start()

    print("--- Jetson Laser Comm Terminal ---")
    try:
        while True:
            msg = input("> ")
            if msg:
                ser.write(msg.encode('utf-8'))
    except KeyboardInterrupt:
        ser.close()

if __name__ == "__main__":
    main()