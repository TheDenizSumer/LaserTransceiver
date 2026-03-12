import sys


def text_to_binary(input_path: str, output_path: str = "output") -> None:
    """Read a text file and write its binary representation to an output file."""
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    with open(output_path, "wb") as f:
        f.write(text.encode("utf-8"))

    print(f"Done! Binary output written to '{output_path}'")
    #print(f"  Characters converted: {len(binary_lines)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python text_to_binary.py <input_file> [output_file]")
        print("  output_file defaults to 'output' if not specified")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output"

    text_to_binary(input_file, output_file)