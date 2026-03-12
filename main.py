from queue import Queue
from outQueue import build_chunk, TYPE_ACK
from readFile import read_bytes
from receiver import receiver
from PacketConstruction import unpack, pack
import asyncio
import threading
import pigpio
import time
import os
import glob

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
TYPE_ACK = 0
TYPE_SB = 1
TYPE_NEXT = 2 # signal from main that an ack has been recived, and to move on to the next chunk
TYPE_DATA = 3

def receiver():
    global GPIO_IN

    RX_PIN = GPIO_IN
    bit_time = 1000          # microseconds
    half_bit = bit_time / 2

    pi = pigpio.pi()

    last_tick = None
    last_level = None
    alreadyShort = False

    bits = []

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

def transmitter():
    def transmit_binary_manchester(packet_data):
        pi.set_mode(GPIO_OUT, pigpio.OUTPUT)
        pi.wave_clear() 
        # add a zero to the beginning.
        pulses = [
            pulses.append(pigpio.pulse(1 << GPIO_OUT, 0, HALF_BIT_TIME)),
            pulses.append(pigpio.pulse(0, 1 << GPIO_OUT, HALF_BIT_TIME))
        ]
            # Data bits (LSB first)
        for i in range(64):
            bit = True if (packet_data >> i) & 1 else False
            if bit == 0:
                # Bit 0: High for half-bit, then Low for half-bit
                pulses.append(pigpio.pulse(1 << GPIO_OUT, 0, HALF_BIT_TIME))
                pulses.append(pigpio.pulse(0, 1 << GPIO_OUT, HALF_BIT_TIME))
            elif bit == 1:
                # Bit 1: Low for half-bit, then High for half-bit
                pulses.append(pigpio.pulse(0, 1 << GPIO_OUT, HALF_BIT_TIME))
                pulses.append(pigpio.pulse(1 << GPIO_OUT, 0, HALF_BIT_TIME))
        
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
        



def create_bytearray_from_bits(bits_list):
    """
    Converts a list of bit-lists (each sub-list is 8 bits) into a byte array.
    """
    byte_array = []
    for binary_list in bits_list:
        number = 0
        # Combine the 8 bits into a single integer (byte value)
        for b in binary_list:
            number = (2 * number) + b # Effectively shifts left and adds the next bit
        # Add the resulting byte value to the array
        byte_array.append(number)
    return bytearray(byte_array)

def file_to_bits(filename):
    with open(filename, "rb") as f:
        while (byte := f.read(1)):
            b = byte[0]
            for i in range(7, -1, -1):
                yield (b >> i) & 1

def pull_bytes(filename, chunk_size=8):
    bitarray = []
    for i in range(8):
        bitarray.append([])
        for bit in file_to_bits(filename):
            bitarray[-1].append(bit)
            if len(bitarray[-1]) == chunk_size:
                break
    return create_bytearray_from_bits(bitarray)
    

def handle_transmission(filename):
    batchNumber = 0
    nextChunk = []
    for bit in file_to_bits(filename):
        nextChunk.append(bit)

async def getPacket():
    while True:
        if not incoming_packets.empty():
            packet_int = incoming_packets.get()
            packet_bytes = packet_int.to_bytes(8, byteorder='big') if isinstance(packet_int, int) else packet_int
            packetType, numID, data, BigError = unpack(packet_bytes)
            
            if packetType == TYPE_DATA and not BigError:
                print(f"\n[RECEIVE] Received valid data packet (ID: {numID})")
                # Process the data as needed
                # For example, you could store it in a buffer until you have a full chunk, then write to file
                
                # Send ACK back to sender
                if numID == 7:
                    ack_packet = pack(TYPE_ACK, numID, b'')  # ACK with same numID and empty data
                    outgoing_packets.put(int.from_bytes(ack_packet, byteorder='big'))
                    print(f"[RECEIVE] Sent ACK for packet ID: {numID}")
                    await asyncio.sleep(0.0001)
            else:
                print(f"\n[RECEIVE] Received invalid packet (Type: {packetType}, Error: {BigError}), ignoring...")



async def send():
    """
    Continuously send chunks of data to the receiver and wait for ACK.
    Retries chunk transmission if ACK is invalid or times out.
    """
    while True:
        # takes 8 sets of 6 bytes (48 bytes total)
        payload = read_bytes(48)

        if not payload:
            # No data available, wait a bit before trying again
            await asyncio.sleep(0.1)
            continue

        # set of 8 packets, each with 6 bytes of data, and header/parity bits added by build_chunk
        chunk = build_chunk(payload)
        
        ack_received = False
        while not ack_received:
            # Send all 8 packets in the chunk to the outgoing queue
            print(f"\n[SEND] Transmitting chunk with {len(chunk)} packets...")
            for i, packet_bytes in enumerate(chunk):
                # Convert bytes to integer for transmission
                packet_int = int.from_bytes(packet_bytes, byteorder='big')
                outgoing_packets.put(packet_int)
                print(f"  Queued packet {i+1}/8")
            
            # Wait for ACK with timeout
            ack_timeout = 5.0  # seconds
            start_time = time.time()
            
            while (time.time() - start_time) < ack_timeout:
                if not incoming_packets.empty():
                    ack_packet_int = incoming_packets.get()
                    
                    # Convert to bytes and unpack to verify
                    ack_packet_bytes = ack_packet_int.to_bytes(8, byteorder='big') if isinstance(ack_packet_int, int) else ack_packet_int
                    packetType, numID, data, BigError = unpack(ack_packet_bytes)
                    
                    if packetType == TYPE_ACK and not BigError:
                        print(f"[SEND] ✓ Valid ACK received, moving to next chunk")
                        ack_received = True
                        break
                    else:
                        print(f"[SEND] ✗ Invalid ACK (Type: {packetType}, Error: {BigError}), resending chunk...")
                        break  # Break inner loop to resend
                
                await asyncio.sleep(0.01)
            
            if not ack_received:
                print("[SEND] ✗ ACK timeout, resending chunk...")


threading.Thread(target=receiver, daemon=True).start()
threading.Thread(target=transmitter, daemon=True).start()


async def main_loop():
    while True:
        # Check "I-O files" folder for any file named "input" with any extension
        io_dir = os.path.join(os.path.dirname(__file__), "I-O files")
        input_files = glob.glob(os.path.join(io_dir, "input.*"))
        if input_files:
            print("Found input file(s):", input_files)

            # TODO: Add processing for input file(s) here if needed
        

        # example: send ACK
        if need_ack():
            outgoing_packets.put(make_ack())