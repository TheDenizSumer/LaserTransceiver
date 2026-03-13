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
- 500 bit/s default (configurable in `laser_link.py`)

## Troubleshooting: TX works but RX gets nothing

1. **Run the RX monitor** on the receiving Pi:
   ```bash
   python rx_monitor.py
   ```
   Start transmitting from the other Pi. You should see `0`/`1` toggling. If stuck on one value: alignment, wiring, or signal polarity.

2. **Try inverted RX** if your photodiode outputs LOW when the laser is ON:
   ```bash
   RX_INVERTED=1 python main.py
   ```

3. **Check alignment** – laser must hit the photodiode.

4. **Slower link** – edit `BIT_PERIOD_S` in `laser_link.py` (e.g. `0.005` for 200 bit/s).
