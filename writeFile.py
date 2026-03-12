from __future__ import annotations

"""
Utility for writing a single byte to the end of the input file as raw binary.

Behavior:
- Treats the `IO/input` file as a binary stream.
- Given a byte value, it:
  1. Normalizes it to a single byte.
  2. Appends that raw byte to the end of `IO/input`.

Example:
    write_byte(0b10101011)
    # Appends one byte whose bit pattern is 10101011.
"""

import os
from typing import Optional, Union


def _get_input_path(explicit_path: Optional[str] = None) -> str:
    """
    Resolve the path to the input file.

    By default this is `<project_root>/IO/input`, matching `frontend.py`.
    """
    if explicit_path is not None:
        return os.path.abspath(explicit_path)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "IO", "input")


def write_byte(byte_val: Union[int, bytes], *, input_path: Optional[str] = None) -> None:
    """
    Take a single byte and append it (raw binary) to the end of the input file.

    Examples:
        write_byte(0b10101011)
        # Appends one byte with bit pattern 10101011 to IO/input

    Args:
        byte_val: Either an integer in [0, 255] or a one-byte `bytes` object.
        input_path: Optional explicit path to the input file. If not provided,
                    defaults to `<project_root>/IO/input`.
    """
    # Normalize to integer 0-255.
    if isinstance(byte_val, bytes):
        if len(byte_val) != 1:
            raise ValueError("byte_val as bytes must be exactly length 1.")
        value = byte_val[0]
    else:
        value = int(byte_val)
    if not (0 <= value <= 0xFF):
        raise ValueError("byte_val must be in range 0..255.")

    path = _get_input_path(input_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Append raw binary byte to the input file.
    with open(path, "ab") as f:
        f.write(bytes([value]))


__all__ = ["write_byte"]

