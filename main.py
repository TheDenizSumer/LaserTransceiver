from queue import Queue
from receiver import receiver
import threading
import pigpio
import time

pi = pigpio.pi()

if not pi.connected:
    print("Error: pigpiod daemon is not running. Run 'sudo pigpiod'.")
    exit()

incoming_packets = Queue()
outgoing_packets = Queue()


bit_time = 1000          # microseconds
half_bit = bit_time / 2

BIT_RATE = 1 / bit_time
PACKET_BYTE_LENGTH = 8
GPIO_OUT = 27
GPIO_IN = 17
BIT_PERIOD = 1 / BIT_RATE
HALF_BIT_TIME = int(1000000 / BIT_RATE / 2)


def receiver():
    def edge_callback(gpio, level, tick):
        global last_tick, last_level, state, bits, alreadyShort

        if last_tick is None:
            last_tick = tick
            last_level = level
            return

        dt = pigpio.tickDiff(last_tick, tick)
        last_tick = tick
        if dt < half_bit*1.2:
            if bits == []:
                bits.append(0)
            elif alreadyShort:
                alreadyShort = False
                bits.insert(0, bits[-1])
            else:
                alreadyShort = True
        elif dt < bit_time*1.2:
            alreadyShort = False
            bits.insert(0, bits[-1] ^ 1)
        else:
            alreadyShort = False
            packet = int("".join(map(str,bits)), 2)
            incoming_packets.put(packet)
            bits = []

    pi.set_mode(GPIO_IN, pigpio.INPUT)
    cb = pi.callback(GPIO_IN, pigpio.EITHER_EDGE, edge_callback)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cb.cancel()
        pi.stop()

    while True:
        packet = receiver()  # your decoding logic
        if packet:
            incoming_packets.put(packet)

def transmitter():
    def transmit_binary_manchester(packet_data):
        pi.set_mode(GPIO_PIN, pigpio.OUTPUT)
        pi.wave_clear() 
        
        pulses = []
            # Data bits (LSB first)
        for i in range(64):
            bit = True if (packet_data >> i) & 1 else False
            if bit == 0:
                # Bit 0: High for half-bit, then Low for half-bit
                pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
                pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
            elif bit == 1:
                # Bit 1: Low for half-bit, then High for half-bit
                pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
                pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
        
        # Load all pulses into the buffer
        pi.wave_add_generic(pulses)
        
        # Create the wave ID
        wave_id = pi.wave_create()
        
        if wave_id >= 0:
            print(f"Sending: {bin(packet_data)}")
            pi.wave_send_once(wave_id)
            
            # Wait for transmission to finish so the script doesn't close too early
            while pi.wave_tx_busy():
                time.sleep(0.01)
                
            print("Transmission complete.")
            pi.wave_delete(wave_id) # Clean up the Wave ID to save memory
        else:
            print("Failed to create waveform. Too many pulses?")

    while True:
        packet = outgoing_packets.get()
        transmit_binary_manchester(packet)   # convert int (bits) -> laser pulses
        

threading.Thread(target=receiver, daemon=True).start()
threading.Thread(target=transmitter, daemon=True).start()

def main_loop():
    while True:
        if not incoming_packets.empty():
            packet = incoming_packets.get()
            handle_packet(packet)

        # example: send ACK
        if need_ack():
            outgoing_packets.put(make_ack())