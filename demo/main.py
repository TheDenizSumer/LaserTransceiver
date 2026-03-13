"""
Laser File Transfer - Two-way file transfer between Raspberry Pis
via laser diode (GPIO 27) and photodiode (GPIO 17).

Both Pis run this same code. Select a file to send; received files
are displayed automatically.
"""

from __future__ import annotations

import io
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IO_DIR = os.path.join(BASE_DIR, "IO")
INPUT_PATH = os.path.join(IO_DIR, "input")
OUTPUT_PATH = os.path.join(IO_DIR, "output")


def _ensure_io_dir():
    os.makedirs(IO_DIR, exist_ok=True)
    for p in (INPUT_PATH, OUTPUT_PATH):
        if not os.path.exists(p):
            with open(p, "wb") as f:
                f.write(b"")


def _read_and_clear_output() -> Optional[bytes]:
    if not os.path.exists(OUTPUT_PATH):
        return None
    with open(OUTPUT_PATH, "rb+") as f:
        data = f.read()
        if not data:
            return None
        f.seek(0)
        f.truncate(0)
    return data


def _write_input(data: bytes) -> None:
    _ensure_io_dir()
    with open(INPUT_PATH, "wb") as f:
        f.write(data or b"")


def _is_text(data: bytes) -> bool:
    """Heuristic: mostly printable ASCII/UTF-8."""
    try:
        text = data.decode("utf-8")
        printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
        return printable / max(len(text), 1) > 0.9
    except Exception:
        return False


def _is_image(data: bytes) -> bool:
    magic = {
        b"\x89PNG": "png",
        b"\xff\xd8\xff": "jpeg",
        b"GIF87a": "gif",
        b"GIF89a": "gif",
        b"BM": "bmp",
        b"RIFF": "webp",  # RIFF....WEBP
    }
    for m, _ in magic.items():
        if data.startswith(m):
            return True
    if data[:4] == b"RIFF" and len(data) > 12 and data[8:12] == b"WEBP":
        return True
    return False


class LaserFileTransferApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Laser File Transfer")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._link = None
        self._stop_event = threading.Event()
        self._tx_thread: Optional[threading.Thread] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._tk_image = None
        self._last_input_sig: Optional[tuple] = None
        self._selected_path: Optional[str] = None

        _ensure_io_dir()
        self._build_ui()
        self._start_link_and_threads()
        self._start_input_poll()
        print("[main] Laser File Transfer started. TX=GPIO27, RX=GPIO17")

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Top: Send controls
        top = tk.Frame(self.root, padx=12, pady=8)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        tk.Label(top, text="File:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.file_var = tk.StringVar(value="No file selected")
        tk.Label(top, textvariable=self.file_var, anchor="w", fg="gray").grid(
            row=0, column=1, sticky="ew"
        )
        tk.Button(top, text="Select File", command=self._on_select_file).grid(
            row=0, column=2, padx=(8, 4)
        )
        tk.Button(top, text="Send", command=self._on_send, width=10).grid(
            row=0, column=3, padx=4
        )

        # Middle: Display area
        display_frame = tk.LabelFrame(self.root, text="Received File", padx=8, pady=8)
        display_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)

        self.display_notebook = tk.Frame(display_frame)
        self.display_notebook.grid(row=0, column=0, sticky="nsew")
        self.display_notebook.columnconfigure(0, weight=1)
        self.display_notebook.rowconfigure(0, weight=1)

        self.text_display = ScrolledText(
            self.display_notebook, wrap=tk.WORD, state=tk.DISABLED, height=12
        )
        self.text_display.grid(row=0, column=0, sticky="nsew")

        self.image_label = tk.Label(
            self.display_notebook,
            text="No file received yet.\nSelect a file and click Send on the other Pi.",
            anchor="center",
        )
        self.image_label.grid(row=0, column=0, sticky="nsew")

        self.binary_frame = tk.Frame(self.display_notebook)
        self.binary_frame.grid(row=0, column=0, sticky="nsew")
        self.binary_frame.columnconfigure(0, weight=1)
        self.binary_frame.rowconfigure(0, weight=1)
        self.binary_text = ScrolledText(
            self.binary_frame, wrap=tk.WORD, state=tk.DISABLED, height=8
        )
        self.binary_text.grid(row=0, column=0, sticky="nsew")
        tk.Button(
            self.binary_frame, text="Save to File...", command=self._save_received_binary
        ).grid(row=1, column=0, pady=4)
        self._received_bytes: Optional[bytes] = None

        self._show_placeholder()

        # Status
        self.status_var = tk.StringVar(value="Ready. Select a file and click Send.")
        tk.Label(self.root, textvariable=self.status_var, anchor="w").grid(
            row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.root.columnconfigure(0, weight=1)

    def _show_placeholder(self):
        self.text_display.grid_remove()
        self.image_label.grid()
        self.binary_frame.grid_remove()
        self.image_label.configure(
            image="",
            text="No file received yet.\nSelect a file and click Send on the other Pi.",
        )

    def _show_text(self, data: bytes):
        self.image_label.grid_remove()
        self.binary_frame.grid_remove()
        self.text_display.grid()
        self.text_display.configure(state=tk.NORMAL)
        self.text_display.delete("1.0", tk.END)
        try:
            self.text_display.insert(tk.END, data.decode("utf-8"))
        except Exception:
            self.text_display.insert(tk.END, data.decode("utf-8", errors="replace"))
        self.text_display.configure(state=tk.DISABLED)

    def _show_image(self, data: bytes):
        self.text_display.grid_remove()
        self.binary_frame.grid_remove()
        self.image_label.grid()
        try:
            from PIL import Image, ImageTk
            img = Image.open(io.BytesIO(data))
            img.thumbnail((600, 400))
            self._tk_image = ImageTk.PhotoImage(img)
            self.image_label.configure(image=self._tk_image, text="")
        except Exception as e:
            self.image_label.configure(text=f"Could not display image: {e}")

    def _show_binary(self, data: bytes):
        self.text_display.grid_remove()
        self.image_label.grid_remove()
        self.binary_frame.grid()
        self._received_bytes = data
        preview = data[:512]
        hex_lines = []
        for i in range(0, len(preview), 16):
            chunk = preview[i : i + 16]
            hex_str = " ".join(f"{b:02x}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            hex_lines.append(f"{i:04x}  {hex_str:<48}  {ascii_str}")
        self.binary_text.configure(state=tk.NORMAL)
        self.binary_text.delete("1.0", tk.END)
        self.binary_text.insert(tk.END, "\n".join(hex_lines))
        if len(data) > 512:
            self.binary_text.insert(tk.END, f"\n\n... ({len(data) - 512} more bytes)")
        self.binary_text.configure(state=tk.DISABLED)

    def _save_received_binary(self):
        if not self._received_bytes:
            return
        path = filedialog.asksaveasfilename(
            title="Save received file",
            defaultextension=".bin",
            filetypes=[("All files", "*.*")],
        )
        if path:
            with open(path, "wb") as f:
                f.write(self._received_bytes)
            self.status_var.set(f"Saved to {path}")

    def _on_select_file(self):
        path = filedialog.askopenfilename(title="Select file to send", filetypes=[("All files", "*.*")])
        if path:
            self._selected_path = path
            size = os.path.getsize(path)
            self.file_var.set(f"{os.path.basename(path)} ({size} bytes)")
            self.status_var.set(f"Selected: {path}")
            print(f"[main] File selected: {os.path.basename(path)} ({size} bytes)")

    def _on_send(self):
        if not self._selected_path or not os.path.exists(self._selected_path):
            messagebox.showwarning("No file", "Please select a file first.")
            return
        try:
            with open(self._selected_path, "rb") as f:
                data = f.read()
            with open(OUTPUT_PATH, "wb") as f:
                f.write(data)
            self.status_var.set(f"Sending {len(data)} bytes...")
            print(f"[main] Queued {len(data)} bytes for send: {os.path.basename(self._selected_path)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            print(f"[main] Send error: {e}")

    def _start_link_and_threads(self):
        from laser_link import LaserLink, LaserLinkConfig

        # Set RX_INVERTED=1 if photodiode outputs LOW when laser is ON
        rx_inverted = os.environ.get("RX_INVERTED", "").strip() in ("1", "true", "yes")
        if rx_inverted:
            print("[main] RX inverted mode (photodiode LOW = light)")
        config = LaserLinkConfig(rx_inverted=rx_inverted)
        self._link = LaserLink(config=config)
        self._tx_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._rx_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self._tx_thread.start()
        self._rx_thread.start()

    def _sender_loop(self):
        while not self._stop_event.is_set():
            try:
                data = _read_and_clear_output()
                if data and self._link:
                    print(f"[TX] Sending {len(data)} bytes...")
                    self.root.after(0, lambda: self.status_var.set("Sending..."))
                    ok = self._link.send_file_bytes(data)
                    print(f"[TX] {'OK' if ok else 'FAILED'} ({len(data)} bytes)")
                    self.root.after(
                        0,
                        lambda o=ok: self.status_var.set(
                            "Sent successfully." if o else "Send failed (retries exceeded)."
                        ),
                    )
                else:
                    time.sleep(0.25)
            except Exception as e:
                print(f"[TX] Error: {e}")
                self.root.after(0, lambda err=str(e): self.status_var.set(f"Send error: {err}"))
                time.sleep(0.5)

    def _receiver_loop(self):
        while not self._stop_event.is_set():
            try:
                if self._link:
                    data = self._link.receive_one_file(max_wait_s=5.0)
                    if data:
                        print(f"[RX] Received {len(data)} bytes")
                        _write_input(data)
            except Exception as e:
                print(f"[RX] Error: {e}")
            time.sleep(0.1)

    def _start_input_poll(self):
        self.root.after(250, self._poll_input)

    def _poll_input(self):
        try:
            st = os.stat(INPUT_PATH)
            sig = (st.st_mtime_ns, st.st_size)
            if st.st_size > 0 and sig != self._last_input_sig:
                with open(INPUT_PATH, "rb") as f:
                    data = f.read()
                self._last_input_sig = sig
                self._display_received(data)
            elif st.st_size == 0:
                self._last_input_sig = sig
        except FileNotFoundError:
            _ensure_io_dir()
        except Exception:
            pass
        self.root.after(250, self._poll_input)

    def _display_received(self, data: bytes):
        self.status_var.set(f"Received {len(data)} bytes.")
        if _is_image(data):
            print(f"[RX] Displaying as image ({len(data)} bytes)")
            self._show_image(data)
        elif _is_text(data):
            print(f"[RX] Displaying as text ({len(data)} bytes)")
            self._show_text(data)
        else:
            print(f"[RX] Displaying as binary ({len(data)} bytes)")
            self._show_binary(data)

    def _on_close(self):
        print("[main] Shutting down...")
        self._stop_event.set()
        time.sleep(0.3)
        if self._link:
            self._link.cleanup()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = LaserFileTransferApp()
    app.run()


if __name__ == "__main__":
    main()
