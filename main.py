from queue import Queue
import asyncio
import threading
import time
import os

import pigpio

from outQueue import build_chunk, TYPE_ACK, TYPE_DATA, TYPE_SB
from readFile import read_bytes
from PacketConstruction import unpack, pack
from writeFile import write_byte

pi = pigpio.pi()

if not pi.connected:
    print("Error: pigpiod daemon is not running. Run 'sudo pigpiod'.")
    raise SystemExit("pigpiod is not running. Start it with: sudo pigpiod")

incoming_packets: "Queue[int]" = Queue()
outgoing_packets: "Queue[int]" = Queue()


bit_time = 1000          # microseconds
half_bit = bit_time / 2

BIT_RATE = 1_000_000 / bit_time  # bits per second
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
    """
    Manchester receiver running in its own thread.
    It reconstructs 64‑bit packets (as int) and pushes them to `incoming_packets`.
    """
    RX_PIN = GPIO_IN
    local_bit_time = bit_time
    local_half_bit = local_bit_time / 2

    rx_pi = pigpio.pi()
    if not rx_pi.connected:
        print("Receiver: pigpiod not running.")
        return

    last_tick = None
    alreadyShort = False
    bits = []

    def edge_callback(gpio, level, tick):
        nonlocal last_tick, alreadyShort, bits

        if last_tick is None:
            last_tick = tick
            return

        dt = pigpio.tickDiff(last_tick, tick)
        last_tick = tick
        if dt < local_half_bit * 1.2:
            if bits == []:
                bits.append(0)
            elif alreadyShort:
                alreadyShort = False
                bits.append(bits[-1])
            else:
                alreadyShort = True
        elif dt < local_bit_time * 1.2:
            alreadyShort = False
            bits.append(bits[-1] ^ 1)
        else:
            alreadyShort = False
            if bits:
                try:
                    packet = int("".join(map(str, bits)), 2)
                    incoming_packets.put(packet)
                except ValueError:
                    pass
            bits = []

    rx_pi.set_mode(RX_PIN, pigpio.INPUT)
    cb = rx_pi.callback(RX_PIN, pigpio.EITHER_EDGE, edge_callback)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cb.cancel()
        rx_pi.stop()


def transmitter():
    """
    Manchester transmitter running in its own thread.
    It pulls 64‑bit packet ints from `outgoing_packets` and emits them using pigpio waves.
    """

    def transmit_binary_manchester(packet_data: int):
        pi.set_mode(GPIO_OUT, pigpio.OUTPUT)
        pi.wave_clear()
        pulses = []

        # Data bits (LSB first)
        for i in range(64):
            bit = 1 if ((packet_data >> i) & 1) else 0
            if bit == 0:
                # Bit 0: High for half-bit, then Low for half-bit
                pulses.append(pigpio.pulse(1 << GPIO_OUT, 0, HALF_BIT_TIME))
                pulses.append(pigpio.pulse(0, 1 << GPIO_OUT, HALF_BIT_TIME))
            else:
                # Bit 1: Low for half-bit, then High for half-bit
                pulses.append(pigpio.pulse(0, 1 << GPIO_OUT, HALF_BIT_TIME))
                pulses.append(pigpio.pulse(1 << GPIO_OUT, 0, HALF_BIT_TIME))

        # Load all pulses into the buffer
        pi.wave_add_generic(pulses)

        # Create the wave ID
        wave_id = pi.wave_create()

        if wave_id >= 0:
            print(f"[TX] Sending: {packet_data:064b}")
            pi.wave_send_once(wave_id)

            # Wait for transmission to finish so the script doesn't close too early
            while pi.wave_tx_busy():
                time.sleep(0.001)

            print("[TX] Transmission complete.")
            pi.wave_delete(wave_id) # Clean up the Wave ID to save memory
        else:
            print("[TX] Failed to create waveform. Too many pulses?")

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
    # currently unused – kept for reference


async def getPacket():
    """
    Consume packets from `incoming_packets`, decode them, and:
    - On TYPE_SB: clear IO/input and reset receive buffer.
    - On TYPE_DATA: append payload bytes to IO/input (via writeFile).
    - On last data packet in a chunk (ID 7): send an ACK.
    """
    while True:
        if incoming_packets.empty():
            await asyncio.sleep(0.001)
            continue

        packet_int = incoming_packets.get()
        packet_bytes = (
            packet_int.to_bytes(8, byteorder="big")
            if isinstance(packet_int, int)
            else packet_int
        )
        packetType, numID, data, BigError = unpack(packet_bytes)

        if BigError:
            print(f"[RX] Discarding packet with uncorrectable error (type={packetType}, id={numID})")
            continue

        if packetType == TYPE_SB:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            input_path = os.path.join(base_dir, "IO", "input")
            os.makedirs(os.path.dirname(input_path), exist_ok=True)
            with open(input_path, "wb") as f:
                f.write(b"")
            print("[RX] Received SB – cleared IO/input for new image")
            continue

        if packetType == TYPE_DATA:
            for b in data:
                write_byte(b)
            print(f"[RX] Received DATA packet id={numID}")

            if numID == 7:
                ack_packet = pack(TYPE_ACK, 0, b"\x00" * 6)
                outgoing_packets.put(int.from_bytes(ack_packet, byteorder="big"))
                print("[RX] Sent ACK for completed chunk")

        # TYPE_ACK is consumed only by `send()`, which also reads from
        # `incoming_packets`. We intentionally ignore ACKs here to avoid
        # racing over the same queue.


async def send():
    """
    Continuously send chunks of data to the receiver and wait for ACK.
    Retries chunk transmission if ACK is invalid or times out.
    """
    sent_sb_for_current_stream = False
    idle_cycles = 0

    while True:
        payload = read_bytes(48)

        if not payload:
            idle_cycles += 1
            if idle_cycles > 20:
                sent_sb_for_current_stream = False
                idle_cycles = 0
            await asyncio.sleep(0.1)
            continue

        idle_cycles = 0

        if not sent_sb_for_current_stream:
            sb_packet = pack(TYPE_SB, 0, b"\x00" * 6)
            outgoing_packets.put(int.from_bytes(sb_packet, byteorder="big"))
            sent_sb_for_current_stream = True
            print("[SEND] Transmitting SB (start of image)")

        chunk = build_chunk(payload)

        ack_received = False
        while not ack_received:
            print(f"[SEND] Transmitting chunk with {len(chunk)} packets...")
            for i, packet_bytes in enumerate(chunk):
                packet_int = int.from_bytes(packet_bytes, byteorder="big")
                outgoing_packets.put(packet_int)
                print(f"  Queued packet {i+1}/8")

            ack_timeout = 5.0  # seconds
            start_time = time.time()

            while (time.time() - start_time) < ack_timeout:
                if not incoming_packets.empty():
                    ack_packet_int = incoming_packets.get()
                    ack_packet_bytes = (
                        ack_packet_int.to_bytes(8, byteorder="big")
                        if isinstance(ack_packet_int, int)
                        else ack_packet_int
                    )
                    packetType, numID, data, BigError = unpack(ack_packet_bytes)

                    if packetType == TYPE_ACK and not BigError:
                        print("[SEND] ✓ Valid ACK received, moving to next chunk")
                        ack_received = True
                        break
                    else:
                        print(
                            f"[SEND] ✗ Invalid ACK (Type: {packetType}, Error: {BigError}), "
                            "resending chunk..."
                        )
                        break

                await asyncio.sleep(0.01)

            if not ack_received:
                print("[SEND] ✗ ACK timeout, resending chunk...")


async def main() -> None:
    threading.Thread(target=receiver, daemon=True).start()
    threading.Thread(target=transmitter, daemon=True).start()
    await asyncio.gather(getPacket(), send())


if __name__ == "__main__":
    asyncio.run(main())