"""
Bit-banged laser link for Raspberry Pi using GPIO 27 (TX / laser diode)
and GPIO 17 (RX / photodiode comparator).

Protocol: UART-style framing with CRC16, stop-and-wait ARQ.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

GPIO_TX_PIN = 27  # Laser output
GPIO_RX_PIN = 17  # Photodiode input

BIT_PERIOD_S = 0.002  # 500 bit/s; slower = more reliable for photodiode circuits
SOF_DATA = 0xA1
SOF_ACK = 0xA2
MAX_PAYLOAD = 64
ACK_TIMEOUT_S = 0.5
MAX_RETRIES = 8


def _crc16_ccitt(data: bytes, *, poly: int = 0x1021, init: int = 0xFFFF) -> int:
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
    try:
        import RPi.GPIO as GPIO
        print("[laser_link] Using RPi.GPIO (real hardware)")
        return GPIO
    except Exception:
        print("[laser_link] RPi.GPIO not available, using mock (no real TX/RX)")
        class _MockGPIO:
            BCM, OUT, IN, LOW, HIGH = "BCM", "OUT", "IN", 0, 1
            def setmode(self, *_): pass
            def setup(self, *_): pass
            def output(self, *_): pass
            def input(self, *_): return 0
            def cleanup(self): pass
        return _MockGPIO()


GPIO = _try_import_gpio()


@dataclass
class LaserLinkConfig:
    tx_pin: int = GPIO_TX_PIN
    rx_pin: int = GPIO_RX_PIN
    bit_period_s: float = BIT_PERIOD_S
    rx_inverted: bool = False  # True if photodiode outputs LOW when laser ON


class LaserLink:
    def __init__(self, config: Optional[LaserLinkConfig] = None) -> None:
        self.config = config or LaserLinkConfig()
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.config.tx_pin, GPIO.OUT)
        GPIO.setup(self.config.rx_pin, GPIO.IN)
        GPIO.output(self.config.tx_pin, GPIO.LOW)

    def _send_bit(self, bit: int) -> None:
        GPIO.output(self.config.tx_pin, GPIO.HIGH if bit else GPIO.LOW)
        time.sleep(self.config.bit_period_s)

    def _read_pin(self) -> int:
        raw = GPIO.input(self.config.rx_pin)
        return (1 - raw) if self.config.rx_inverted else raw

    def _send_byte(self, value: int) -> None:
        value &= 0xFF
        self._send_bit(1)  # Start bit
        for i in range(8):
            self._send_bit((value >> i) & 0x01)
        self._send_bit(0)  # Stop bit
        GPIO.output(self.config.tx_pin, GPIO.LOW)

    def _read_byte(self, timeout_s: float) -> Optional[int]:
        deadline = time.time() + timeout_s
        poll = max(self.config.bit_period_s / 10.0, 0.00005)
        while time.time() < deadline:
            if self._read_pin():
                break
            time.sleep(poll)
        else:
            return None
        time.sleep(self.config.bit_period_s * 1.5)
        value = 0
        for i in range(8):
            value |= ((1 if self._read_pin() else 0) << i)
            time.sleep(self.config.bit_period_s)
        time.sleep(self.config.bit_period_s)
        return value & 0xFF

    def _send_data_packet(self, seq: int, payload: bytes) -> None:
        if len(payload) > 0xFF:
            raise ValueError("Payload too large")
        length = len(payload)
        header = bytes([seq & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
        crc = _crc16_ccitt(header + payload)
        frame = bytes([SOF_DATA]) + header + payload + bytes([(crc >> 8) & 0xFF, crc & 0xFF])
        for b in frame:
            self._send_byte(b)

    def _send_ack(self, seq: int, status: int = 0) -> None:
        header = bytes([seq & 0xFF, status & 0xFF])
        crc = _crc16_ccitt(header)
        frame = bytes([SOF_ACK]) + header + bytes([(crc >> 8) & 0xFF, crc & 0xFF])
        for b in frame:
            self._send_byte(b)

    def _recv_packet(self, timeout_s: float) -> Optional[Tuple[int, int, bytes]]:
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
                return None
            return ptype, seq, bytes(payload)

        seq = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        status = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        if seq is None or status is None:
            return None
        crc_hi = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        crc_lo = self._read_byte(timeout_s=ACK_TIMEOUT_S)
        if crc_hi is None or crc_lo is None:
            return None
        crc_recv = ((crc_hi & 0xFF) << 8) | (crc_lo & 0xFF)
        if crc_recv != _crc16_ccitt(bytes([seq & 0xFF, status & 0xFF])):
            return None
        return ptype, seq, bytes([status & 0xFF])

    def send_file_bytes(self, data: bytes) -> bool:
        total_len = len(data)
        stream = total_len.to_bytes(4, "big") + data
        num_packets = (len(stream) + MAX_PAYLOAD - 1) // MAX_PAYLOAD
        seq, offset = 0, 0
        print(f"[link] TX: {total_len} bytes in {num_packets} packets")
        while offset < len(stream):
            chunk = stream[offset : offset + MAX_PAYLOAD]
            for attempt in range(MAX_RETRIES):
                self._send_data_packet(seq, chunk)
                pkt = self._recv_packet(timeout_s=ACK_TIMEOUT_S)
                if pkt is None:
                    if attempt < MAX_RETRIES - 1:
                        print(f"[link] TX seq {seq}: no ACK, retry {attempt + 1}/{MAX_RETRIES}")
                    continue
                ptype, ack_seq, ack_payload = pkt
                if ptype != SOF_ACK or (ack_seq & 0xFF) != (seq & 0xFF):
                    continue
                if (ack_payload[0] if ack_payload else 1) == 0:
                    offset += len(chunk)
                    seq = (seq + 1) & 0xFF
                    if seq % 8 == 0 or offset >= len(stream):
                        print(f"[link] TX progress: {offset}/{len(stream)} bytes")
                    break
            else:
                print(f"[link] TX FAILED at seq {seq} (retries exceeded)")
                return False
        print(f"[link] TX complete")
        return True

    def receive_one_file(self, *, max_wait_s: float = 60.0) -> Optional[bytes]:
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
                continue
            self._send_ack(seq, status=0)
            if (seq & 0xFF) != (expected_seq & 0xFF):
                continue
            buffer.extend(payload)
            expected_seq = (expected_seq + 1) & 0xFF
            if expected_total_len is None and len(buffer) >= 4:
                expected_total_len = int.from_bytes(buffer[:4], "big")
                print(f"[link] RX: expecting {expected_total_len} bytes")
            if expected_total_len is not None:
                data_len = len(buffer) - 4
                if data_len >= expected_total_len:
                    print(f"[link] RX complete: {expected_total_len} bytes")
                    return bytes(buffer[4 : 4 + expected_total_len])
        return None

    def cleanup(self) -> None:
        GPIO.cleanup()
