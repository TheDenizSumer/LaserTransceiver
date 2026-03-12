from __future__ import annotations

"""
Utility for reading a specified number of **bytes** from the start of the output file.

Behavior:
- Treats the `IO/output` file as raw binary data.
- Given an integer N, it:
  1. Reads the first N bytes from the file.
  2. Removes those bytes from the file (shifts the file contents left by N bytes).
  3. Returns the N bytes as a list of 1-byte `bytes` objects.
"""

import os
from typing import Optional


def _get_output_path(explicit_path: Optional[str] = None) -> str:
    """
    Resolve the path to the output file.

    By default this is `<project_root>/IO/output`, matching `frontend.py`.
    """
    if explicit_path is not None:
        return os.path.abspath(explicit_path)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "IO", "output")


def read_bytes(n_bytes: int, *, output_path: Optional[str] = None) -> list[bytes]:
    """
    Read the first `n_bytes` bytes from the output file, remove them from the file,
    and return those bytes.

    - If the file contains fewer than `n_bytes` bytes, all available bytes are used.

    Args:
        n_bytes: Number of bytes to consume from the start of the file.
        output_path: Optional explicit path to the output file. If not provided,
                     defaults to `<project_root>/IO/output`.

    Returns:
        A list of 1-byte `bytes` objects, up to length `n_bytes`.
    """
    if n_bytes <= 0:
        return []

    path = _get_output_path(output_path)

    # Read current contents as raw bytes.
    try:
        with open(path, "rb+") as f:
            data = f.read()

            if not data:
                return []

            # Take up to n_bytes from the front.
            take = data[:n_bytes]
            remaining = data[n_bytes:]

            # Rewind and overwrite the file with the remaining bits.
            f.seek(0)
            f.truncate(0)
            f.write(remaining)

    except FileNotFoundError as e:
        raise FileNotFoundError(f"Output file not found at: {path}") from e

    # Return as a list of 1-byte `bytes` objects.
    return bytearray(take)
    #return [bytes([b]) for b in take]


__all__ = ["read_bytes"]

