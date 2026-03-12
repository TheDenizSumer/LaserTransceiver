header_color = '\033[91m'    #red - header bits
data_color = '\033[92m'      #green - data bits
parity_color = '\033[94m'    #blue - parity bits
overall_color = '\033[95m'   #magenta - overall parity bit
unused_color = '\033[90m'    #gray - unused
highlight_color = '\033[93m' #yellow - flipped bits
reset = '\033[0m'


def pack(packetType: int, numID: int, data: bytes) -> bytes:
    #if(packetType == 0): #normal data packet

    #numID: 3 bits, packetType: 3 bits, 3 bits unused, data: 48 bits
    msg = packetType << 54 | numID << 51 | int.from_bytes(data, 'big')

    codeword = buildParityWord(msg)
    
    overallParity = 0
    for i in range(63):
        overallParity ^= (codeword >> i) & 1 #0 if even number of 1s, 1 if odd number of 1s
      
    word = overallParity << 63 | codeword

    #word = flipBitStream(word)
    
    return word.to_bytes(8, byteorder='big')


def unpack(packet: bytes):
    BigError = False
    
    codeword = int.from_bytes(packet, 'big')

    overallParity = (codeword >> 63) & 1
    
    overallMask = (1 << 63) - 1 
    codeword = codeword & overallMask
    
    #print(f"Unpacked Data: {codeword:063b}")
    
    syndrome = 0
    for i in range(6):
        pos = 1 << i
        parity = 0
        for bit in range(1, 64):
            if bit & pos:
                parity ^= (codeword >> (63 - bit)) & 1
        syndrome |= (parity << i)
    
    
    expected_overall = 0
    for i in range(63):
        expected_overall ^= (codeword >> i) & 1
    if syndrome == 0:
        if expected_overall != overallParity:
            BigError = True
    else:
        error_pos = syndrome
        if 1 <= error_pos <= 63:
            codeword ^= 1 << (63 - error_pos)
            corrected_overall = 0
            for i in range(63):
                corrected_overall ^= (codeword >> i) & 1
            if corrected_overall != overallParity:
                BigError = True
        else:
            BigError = True

    msg = 0
    data_index = 0
    for bit in range(1, 64):
        if (bit & (bit - 1)) != 0:
            bit_val = (codeword >> (63 - bit)) & 1
            msg |= bit_val << data_index
            data_index += 1
     
    data = (msg & 0xFFFFFFFFFFFF).to_bytes(6, byteorder='big')
    unused = (msg >> 48) & 0x7
    numID = (msg >> 51) & 0x7
    packetType = (msg >> 54) & 0x7

#    print(f"Data:          {header_color}Type: {packetType}{reset} {header_color}ID: {numID}{reset} {data_color}Data: {hex(data)}{reset}")
    
    return packetType, numID, data, BigError


def buildParityWord(msg: int) -> int:
    parityWord = 0
    data_index = 0
    
    #print(f"Message:       {msg:033b}")
    
    for bit in range(1, 64):
        if (bit & (bit - 1)) == 0:  #parity position, powers of 2
            continue
        bit_val = (msg >> data_index) & 1
        parityWord |= bit_val << (63 - bit)
        data_index += 1
        
    #print(f"before parity: {parityWord:039b}")
    
    # compute parity bits
    for i in range(6):
        pos = 1 << i
        parity = 0
        for bit in range(1, 64):
            if bit & pos:
                parity ^= (parityWord >> (63 - bit)) & 1 #idk
        parityWord |= parity << (63 - pos)
        
    #print(f"with parity:   {parityWord:039b}")

    return parityWord


def printPacket(packet: bytes, flipped_bits: list[int] = []):

    
    if(flipped_bits):
        print(f"Corrupted:     ", end="")
    else:
        print(f"Packed Data:   ", end="")
    
    for i in range(64):
        bit_val = (int.from_bytes(packet, 'big') >> (63 - i)) & 1
        
        color = unused_color
        
        if i > 57: #header
            color = header_color
            
        if i < 55 and i > 2: #data
            color = data_color
            
        if i in [1, 2, 4, 8, 16, 32]:  # parity bit positions
            color = parity_color
            
        if i == 0:  # overall parity bit
            color = overall_color

        if i in flipped_bits:
            color = highlight_color
            
        print(f"{color}{bit_val}{reset}", end="")

    print() #new line
    
# test
if __name__ == "__main__":
    packetType = 0
    numID = 1
    data = 0xABCDEFABCDEF
    flippedBits = [22]

    print(f"Data:          {header_color}Type: {packetType}{reset} {header_color}ID: {numID}{reset} {data_color}Data: {hex(data)}{reset}")

    packet = pack(packetType, numID, data)
    printPacket(packet)

    corrupted_packet = int.from_bytes(packet, 'big')
    for i in flippedBits:
        corrupted_packet ^= (1 << 63-i)
    corrupted_packet = corrupted_packet.to_bytes(8, byteorder='big')

    printPacket(corrupted_packet, flippedBits)

    newPacket = unpack(corrupted_packet)
    
    if(newPacket[3]):
        print(f"{highlight_color}BIG Error{reset}")
    else:
        print(f"Unpacked Data: {header_color}Type: {newPacket[0]}{reset} {header_color}ID: {newPacket[1]}{reset} {data_color}Data: {hex(newPacket[2])}{reset}")
