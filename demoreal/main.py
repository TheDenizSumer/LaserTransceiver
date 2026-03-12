from __future__ import annotations

"""
Entry point for the laser transceiver backend.

This script is intended to run on BOTH Raspberry Pis.

Responsibilities:
- Watch `IO/output` for outbound image bytes written by `frontend.py`.
- When `IO/output` becomes non‑empty, read its contents, clear the file,
  and send those bytes over the laser link with error‑checked packets.
- In parallel, listen on the laser link for an incoming file; when a full
  file is received, overwrite `IO/input` with the bytes so `frontend.py`
  can display the image.

Usage (on each Pi):
    python3 main.py

IMPORTANT:
- Only one side should be actively sending at a time to avoid collisions.
  For lab testing, manually alternate which Pi has data in its `IO/output`.
"""

import os
import threading
import time
from typing import Optional

from laser_link import LaserLink


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IO_DIR = os.path.join(BASE_DIR, "IO")
INPUT_PATH = os.path.join(IO_DIR, "input")
OUTPUT_PATH = os.path.join(IO_DIR, "output")


def _ensure_io_files() -> None:
    os.makedirs(IO_DIR, exist_ok=True)
    for path in (INPUT_PATH, OUTPUT_PATH):
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(b"")


def _read_and_clear_output() -> Optional[bytes]:
    """
    Read all bytes from `IO/output` and then clear the file.
    Returns None if the file is empty.
    """
    if not os.path.exists(OUTPUT_PATH):
        return None

    with open(OUTPUT_PATH, "rb+") as f:
        data = f.read()
        if not data:
            return None
        f.seek(0)
        f.truncate(0)
    return data


def _write_input_file(data: bytes) -> None:
    os.makedirs(IO_DIR, exist_ok=True)
    with open(INPUT_PATH, "wb") as f:
        f.write(data or b"")


def sender_thread(link: LaserLink, stop_event: threading.Event) -> None:
    """
    Periodically check `IO/output` and, when non‑empty, transmit its contents.
    """
    while not stop_event.is_set():
        try:
            data = _read_and_clear_output()
            if data:
                print(f"[sender] Found {len(data)} bytes to send.")
                ok = link.send_file_bytes(data)
                if ok:
                    print("[sender] Transmission complete with ACKs.")
                else:
                    print("[sender] Transmission failed (too many retries).")
            else:
                # Nothing to send; sleep briefly.
                time.sleep(0.25)
        except Exception as e:
            print(f"[sender] Error: {e}")
            time.sleep(0.5)


def receiver_thread(link: LaserLink, stop_event: threading.Event) -> None:
    """
    Continuously wait for incoming files and write them to `IO/input`.
    """
    while not stop_event.is_set():
        try:
            print("[receiver] Waiting for incoming file...")
            file_bytes = link.receive_one_file(max_wait_s=30.0)
            if file_bytes:
                print(f"[receiver] Received file of {len(file_bytes)} bytes.")
                _write_input_file(file_bytes)
            else:
                # Timeout; loop again.
                continue
        except Exception as e:
            print(f"[receiver] Error: {e}")
            time.sleep(0.5)


def main() -> None:
    _ensure_io_files()

    link = LaserLink()

    stop_event = threading.Event()

    tx_thread = threading.Thread(target=sender_thread, args=(link, stop_event), daemon=True)
    rx_thread = threading.Thread(target=receiver_thread, args=(link, stop_event), daemon=True)

    tx_thread.start()
    rx_thread.start()

    print("LaserTransceiver backend running.")
    print("This program will bridge `IO/output` -> laser TX and laser RX -> `IO/input`.")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Shutting down...")
        stop_event.set()
        time.sleep(0.5)
    finally:
        link.cleanup()


if __name__ == "__main__":
    main()

