from __future__ import annotations

"""
Bit–banged laser link for Raspberry Pi using GPIO 27 (TX / laser diode)
and GPIO 17 (RX / photodiode comparator).

Protocol overview
-----------------
- Physical layer: simple UART‑style framing in software.
  * Idle line: LOW (laser off).
  * Start bit: HIGH for one bit period.
  * 8 data bits, LSB first.
  * Stop bit: LOW for one bit period.

- Packet format (DATA):
  [SOF=0xA1][seq][len_hi][len_lo][payload bytes ...][crc_hi][crc_lo]
    * seq: 0–255, stop‑and‑wait ARQ (sender increments per packet).
    * len: payload length (0–255).
    * CRC16‑CCITT over seq, len_hi, len_lo and payload (NOT including SOF).

- Packet format (ACK):
  [SOF_ACK=0xA2][seq][status][crc_hi][crc_lo]
    * status: 0 = OK, 1 = ERROR (currently only 0 is used).
    * CRC16‑CCITT over seq and status.

- File transfer:
  * First 4 bytes of the byte stream are the total file length (big‑endian).
  * Remaining bytes are the file contents.
  * Receiver accumulates until `len(data_bytes) == file_length`, then writes
    them to IO/input and clears any previous contents.

This module is designed to be used by `main.py` on BOTH Pis.
"""

import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

GPIO_TX_PIN = 27
GPIO_RX_PIN = 17

BIT_PERIOD_S = 0.001  # 1 kbit/s nominal; tune as needed.

SOF_DATA = 0xA1
SOF_ACK = 0xA2

MAX_PAYLOAD = 64  # bytes per DATA packet
ACK_TIMEOUT_S = 0.5
MAX_RETRIES = 8


def _crc16_ccitt(data: bytes, *, poly: int = 0x1021, init: int = 0xFFFF) -> int:
    """
    Compute CRC‑16/CCITT‑FALSE over the given data.
    """
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def _try_import_gpio():
    """
    Import RPi.GPIO if available; otherwise provide a no‑op mock so the code can
    still be imported on non‑Pi systems for development.
    """
    try:
        import RPi.GPIO as GPIO  # type: ignore

        return GPIO
    except Exception:
        class _MockGPIO:
            BCM = "BCM"
            OUT = "OUT"
            IN = "IN"
            LOW = 0
            HIGH = 1

            def setmode(self, *_args, **_kwargs):
                pass

            def setup(self, *_args, **_kwargs):
                pass

            def output(self, *_args, **_kwargs):
                pass

            def input(self, *_args, **_kwargs) -> int:
                return 0

            def cleanup(self):
                pass

        return _MockGPIO()


GPIO = _try_import_gpio()


@dataclass
class LaserLinkConfig:
    tx_pin: int = GPIO_TX_PIN
    rx_pin: int = GPIO_RX_PIN
    bit_period_s: float = BIT_PERIOD_S


class LaserLink:
    def __init__(self, config: Optional[LaserLinkConfig] = None) -> None:
        self.config = config or LaserLinkConfig()

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.config.tx_pin, GPIO.OUT)
        GPIO.setup(self.config.rx_pin, GPIO.IN)

        # Ensure TX is idle low.
        GPIO.output(self.config.tx_pin, GPIO.LOW)

    # ----------------- low‑level bit/byte primitives -----------------

    def _send_bit(self, bit: int) -> None:
        GPIO.output(self.config.tx_pin, GPIO.HIGH if bit else GPIO.LOW)
        time.sleep(self.config.bit_period_s)

    def _read_pin(self) -> int:
        return GPIO.input(self.config.rx_pin)

    def _send_byte(self, value: int) -> None:
        """
        UART‑style frame: start(1), 8 data bits LSB‑first, stop(0).
        """
        value &= 0xFF

        # Start bit (HIGH)
        self._send_bit(1)

        # Data bits (LSB first)
        for i in range(8):
            bit = (value >> i) & 0x01
            self._send_bit(bit)

        # Stop bit (LOW)
        self._send_bit(0)

        # Keep line low between bytes
        GPIO.output(self.config.tx_pin, GPIO.LOW)

    def _read_byte(self, timeout_s: float) -> Optional[int]:
        """
        Block until a start bit is detected or timeout.
        Returns the received 8‑bit value, or None on timeout.
        """
        deadline = time.time() + timeout_s
        poll_interval = self.config.bit_period_s / 10.0
        if poll_interval <= 0:
            poll_interval = 0.00005

        # Wait for rising edge (start bit HIGH)
        while time.time() < deadline:
            if self._read_pin():
                break
            time.sleep(poll_interval)
        else:
            return None

        # We are somewhere in the start bit; wait to the middle of bit 0.
        time.sleep(self.config.bit_period_s * 1.5)

        value = 0
        for i in range(8):
            bit = 1 if self._read_pin() else 0
            value |= (bit << i)
            time.sleep(self.config.bit_period_s)

        # One extra stop bit period to re‑synchronize.
        time.sleep(self.config.bit_period_s)
        return value & 0xFF

    # ----------------- packet‑level primitives -----------------

    def _send_data_packet(self, seq: int, payload: bytes) -> None:
        if len(payload) > 0xFF:
            raise ValueError("Payload too large for single packet.")

        length = len(payload)
        header = bytes([seq & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
        crc_val = _crc16_ccitt(header + payload)
        crc_hi = (crc_val >> 8) & 0xFF
        crc_lo = crc_val & 0xFF

        frame = bytes([SOF_DATA]) + header + payload + bytes([crc_hi, crc_lo])
        for b in frame:
            self._send_byte(b)

    def _send_ack(self, seq: int, status: int = 0) -> None:
        header = bytes([seq & 0xFF, status & 0xFF])
        crc_val = _crc16_ccitt(header)
        crc_hi = (crc_val >> 8) & 0xFF
        crc_lo = crc_val & 0xFF
        frame = bytes([SOF_ACK]) + header + bytes([crc_hi, crc_lo])
        for b in frame:
            self._send_byte(b)

    def _recv_packet(self, timeout_s: float) -> Optional[Tuple[int, int, bytes]]:
        """
        Receive a packet.
        Returns:
            (ptype, seq, payload) or None on timeout.
        ptype is SOF_DATA or SOF_ACK.
        """
        start_deadline = time.time() + timeout_s
        while time.time() < start_deadline:
            b = self._read_byte(timeout_s=timeout_s)
            if b is None:
                return None
            if b in (SOF_DATA, SOF_ACK):
                ptype = b
                break
        else:
            return None

        if ptype == SOF_DATA:
            # DATA: [seq][len_hi][len_lo][payload][crc_hi][crc_lo]
            seq = self._read_byte(timeout_s=ACK_TIMEOUT_S)
            len_hi = self._read_byte(timeout_s=ACK_TIMEOUT_S)
            len_lo = self._read_byte(timeout_s=ACK_TIMEOUT_S)
            if seq is None or len_hi is None or len_lo is None:
                return None

            length = ((len_hi & 0xFF) << 8) | (len_lo & 0xFF)
            if length < 0 or length > 0xFF:
                return None

            payload = bytearray()
            for _ in range(length):
                v = self._read_byte(timeout_s=ACK_TIMEOUT_S)
                if v is None:
                    return None
                payload.append(v)

            crc_hi = self._read_byte(timeout_s=ACK_TIMEOUT_S)
            crc_lo = self._read_byte(timeout_s=ACK_TIMEOUT_S)
            if crc_hi is None or crc_lo is None:
                return None

            crc_recv = ((crc_hi & 0xFF) << 8) | (crc_lo & 0xFF)
            header = bytes([seq & 0xFF, len_hi & 0xFF, len_lo & 0xFF])
            if crc_recv != _crc16_ccitt(header + bytes(payload)):
                # Bad CRC; ignore.
                return None

            return ptype, seq, bytes(payload)

        # ACK: [seq][status][crc_hi][crc_lo]
        seq = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        status = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        if seq is None or status is None:
            return None

        crc_hi = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        crc_lo = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        if crc_hi is None or crc_lo is None:
            return None

        crc_recv = ((crc_hi & 0xFF) << 8) | (crc_lo & 0xFF)
        header = bytes([seq & 0xFF, status & 0xFF])
        if crc_recv != _crc16_ccitt(header):
            return None

        return ptype, seq, bytes([status & 0xFF])

    # ----------------- public high‑level API -----------------

    def send_file_bytes(self, data: bytes) -> bool:
        """
        Send a complete file (as bytes) with simple stop‑and‑wait ARQ and CRC16.

        Layout:
        - First 4 bytes: big‑endian file length.
        - Remainder: file contents.

        Returns:
            True if all packets were ACKed, False otherwise.
        """
        total_len = len(data)
        stream = total_len.to_bytes(4, "big") + data

        seq = 0
        offset = 0
        while offset < len(stream):
            chunk = stream[offset : offset + MAX_PAYLOAD]

            for attempt in range(MAX_RETRIES):
                self._send_data_packet(seq, chunk)

                # Wait for ACK for this seq.
                pkt = self._recv_packet(timeout_s=ACK_TIMEOUT_S)
                if pkt is None:
                    continue
                ptype, ack_seq, ack_payload = pkt
                if ptype != SOF_ACK:
                    continue
                if (ack_seq & 0xFF) != (seq & 0xFF):
                    continue
                status = ack_payload[0] if ack_payload else 1
                if status == 0:
                    # Good ACK.
                    offset += len(chunk)
                    seq = (seq + 1) & 0xFF
                    break
            else:
                # Too many failed attempts.
                return False

        return True

    def receive_one_file(self, *, max_wait_s: float = 60.0) -> Optional[bytes]:
        """
        Block until a full file has been received or timeout.

        Returns:
            The file bytes, or None on timeout/failure.
        """
        start_time = time.time()
        expected_total_len: Optional[int] = None
        buffer = bytearray()
        expected_seq = 0

        while time.time() - start_time < max_wait_s:
            pkt = self._recv_packet(timeout_s=ACK_TIMEOUT_S)
            if pkt is None:
                continue
            ptype, seq, payload = pkt

            if ptype != SOF_DATA:
                # Ignore unexpected ACKs here; sender handles them.
                continue

            # Send ACK immediately (even if duplicate).
            self._send_ack(seq, status=0)

            if (seq & 0xFF) != (expected_seq & 0xFF):
                # Duplicate or out‑of‑order; ignore for data, ACK already sent.
                continue

            buffer.extend(payload)
            expected_seq = (expected_seq + 1) & 0xFF

            if expected_total_len is None and len(buffer) >= 4:
                expected_total_len = int.from_bytes(buffer[:4], "big")

            if expected_total_len is not None:
                data_len = len(buffer) - 4
                if data_len >= expected_total_len:
                    return bytes(buffer[4 : 4 + expected_total_len])

        return None

    def cleanup(self) -> None:
        GPIO.cleanup()


__all__ = ["LaserLink", "LaserLinkConfig"]

