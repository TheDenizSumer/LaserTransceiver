# Laser File Transfer Demo

Two-way file transfer between Raspberry Pis via laser diode (GPIO 27) and photodiode (GPIO 17).

## Hardware

- **GPIO 27**: Laser diode output (TX)
- **GPIO 17**: Photodiode input (RX)

## Setup

```bash
pip install -r requirements.txt
```

## Usage

Run on **both** Pis:

```bash
python main.py
```

1. **Sender**: Click "Select File", choose a file, then "Send"
2. **Receiver**: The file appears automatically in the display area

## Display

- **Text files**: Shown in a scrollable text view
- **Images** (PNG, JPEG, GIF, BMP, WebP): Rendered in the UI
- **Binary**: Hex dump preview + "Save to File" button

## Protocol

- UART-style framing (start bit, 8 data bits, stop bit)
- CRC16-CCITT for error detection
- Stop-and-wait ARQ with retries
- 1 kbit/s default (configurable in `laser_link.py`)
