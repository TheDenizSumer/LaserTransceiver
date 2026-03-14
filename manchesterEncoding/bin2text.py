def text_to_bits(text):
    bits = []
    for char in text:
        bin_val = format(ord(char), '08b') 
        bits.extend([int(bit) for bit in bin_val])
    return bits

def bits_to_text(bits):
    chars = []
    for i in range(0, len(bits), 8):
        byte_chunk = bits[i:i+8]
        if len(byte_chunk) < 8:
            break
        
        bit_str = "".join(map(str, byte_chunk))
        chars.append(chr(int(bit_str, 2)))
        
    return "".join(chars)

# --- Quick Test ---
msg = "Hello"
string = "100001100101011011000110110001101111"
string = "0100" + string
bits = [int(b) for b in string]


bit_list = text_to_bits(msg)
for b in bit_list:
    print(b, end="")
print()
print(string)
decoded = bits_to_text(bits)

print(f"Text:    {msg}")
print(f"Bits:    {bits}")
print(f"Decoded: {decoded}")