def text_to_bits(text):
    """Converts a string to a list of 1s and 0s."""
    bits = []
    for char in text:
        # Convert char to 8-bit binary string, then to list of ints
        bin_val = format(ord(char), '08b') 
        bits.extend([int(bit) for bit in bin_val])
    return bits

def bits_to_text(bits):
    """Converts a list of 1s and 0s back to a string."""
    chars = []
    # Loop through the list in steps of 8
    for i in range(0, len(bits), 8):
        byte_chunk = bits[i:i+8]
        if len(byte_chunk) < 8:
            break
        
        # Join bits into a string and convert from base 2 to integer
        bit_str = "".join(map(str, byte_chunk))
        chars.append(chr(int(bit_str, 2)))
        
    return "".join(chars)

# --- Quick Test ---
msg = "Hello!"
bit_list = text_to_bits(msg)
decoded = bits_to_text(bit_list)

print(f"Text:    {msg}")
print(f"Bits:    {bit_list}")
print(f"Decoded: {decoded}")