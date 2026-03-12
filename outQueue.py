import asyncio

from PacketConstruction import pack
import pigpio

pi = pigpio.pi()

# Type bits, values determine by the protocol designed
bit_time = 500 # mircoseconds
BIT_PERIOD = bit_time * 1/1000000 # convert to seconds
GPIO_OUT = 27
TYPE_ACK = 0
TYPE_SB = 1
TYPE_NEXT = 2 # signal from main that an ack has been recived, and to move on to the next chunk
TYPE_DATA = 3

pi.set_mode(GPIO_OUT, pigpio.OUTPUT)

async def transmitPacket(packet_data):

    # Data bits (LSB first)
    for i in range(64):
        bit = True if (packet_data >> i) & 1 else False
        print(bit)
        if bit == 1:
            pi.write(GPIO_OUT, 0)
            await asyncio.sleep(BIT_PERIOD/2)
            pi.write(GPIO_OUT, 1)
            await asyncio.sleep(BIT_PERIOD/2)
        else:
            pi.write(GPIO_OUT, 1)
            await asyncio.sleep(BIT_PERIOD/2)
            pi.write(GPIO_OUT, 0)
            await asyncio.sleep(BIT_PERIOD/2)

    # short pause after whole packet to allow receiver to sync
    await asyncio.sleep(BIT_PERIOD*3)

def build_chunk(raw_bytes):
    packets = []
    
    # pad with 0's
    data = raw_bytes[:48].ljust(48, b'\x00')
    
    # build 8 data packets
    for i in range(8):
        # extract 6 bytes per packet
        payload = data[i*6 : (i+1)*6]
        
        #header = bytes([i]) # Placeholder header
        #parity = b'\x00'    # Placeholder parity
        #packet = header + payload + parity

        packetType = TYPE_DATA #temp
        numID = i 

        packet = pack(packetType, numID, payload)

        packets.append(packet)

    return packets

async def outLaserWorker(queue):
    print("outLaser Worker Started")

    rawBuffer = bytearray()
    activeChunk = [] # the packets in the current chunk
    chunkIndex = 0 # current position in the chunk

    while True:
        while not queue.empty():
            packetType, packetData = queue.get_nowait()
            
            if packetType == TYPE_ACK:
                # CLEARLY DENOTE THE INTERRUPT
                print(f"\n>>> sending ack now: {packetData}")
                await transmitPacket(packetData)
            
            elif packetType == TYPE_NEXT:
                print("\n>>> ack recived, moving on to next chunk")
                activeChunk = []
                
            elif packetType == TYPE_SB:
                print("\n>>> sending special boy")
                
            elif packetType == TYPE_DATA:
                print(f"\n>>> adding {len(packetData)} bytes of data to raw buffer")
                rawBuffer.extend(packetData)
                
            queue.task_done()
        
        if not activeChunk and len(rawBuffer) > 0: #there is data to send
            chunkBytes = rawBuffer[:48] # 8 packets * 6 bytes/packet = 48 bytes
            del rawBuffer[:48] # delete what was claimed
            activeChunk = build_chunk(chunkBytes)
            chunkIndex = 0
        
        if activeChunk:
            # the packet in raw 1's and 0's form
            rawPacket = ''.join(f'{byte:08b}' for byte in activeChunk[chunkIndex])
            print(f"    [TX] Sending Packet {chunkIndex} | Raw: {rawPacket} | utf-8: {activeChunk[chunkIndex]}")
            await transmitPacket(activeChunk[chunkIndex])
            chunkIndex = (chunkIndex + 1) % 8

        else:
            # proof of life signal
            print(".", end="", flush=True)
            await asyncio.sleep(0.1)