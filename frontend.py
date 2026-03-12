"""
Simple front-end UI for LaserTransceiver.

UI elements:
- Image display area
- Upload button: pick a local image file and display it
- Send button: stub hook for future integration

Key API:
- LaserTransceiverFrontend.set_image(path): display an image in the UI.
  This is called by the Upload button, and can also be called by other code.
"""

from __future__ import annotations

import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Optional


class LaserTransceiverFrontend:
    def __init__(
        self,
        *,
        title: str = "LaserTransceiver Frontend",
        on_send: Optional[Callable[[], None]] = None,
        input_path: Optional[str] = None,
        output_path: Optional[str] = None,
        poll_input_ms: int = 250,
        window_size: tuple[int, int] = (900, 600),
    ) -> None:
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{window_size[0]}x{window_size[1]}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Optional callback invoked when "Send" is pressed.
        self._on_send = on_send

        # Where to read/write binary image data (organized under IO/ by default).
        base_dir = os.path.dirname(os.path.abspath(__file__))
        io_dir = os.path.join(base_dir, "IO")
        # Allow custom paths to override, but default to IO/input and IO/output.
        self.input_path = os.path.abspath(input_path or os.path.join(io_dir, "input"))
        self.output_path = os.path.abspath(output_path or os.path.join(io_dir, "output"))
        self.poll_input_ms = poll_input_ms
        # Signature used to detect changes in `input` across polls.
        # Use nanosecond timestamps to avoid missing fast successive writes.
        self._last_input_sig: tuple[int, int] | None = None  # (mtime_ns, size)

        # Keep a reference to the active image object to prevent garbage collection.
        self._tk_image = None
        self._pil_image = None  # original PIL image (if loaded)
        self._image_path: Optional[str] = None
        self._image_bytes: Optional[bytes] = None
        self._render_after_id: Optional[str] = None

        self._build_ui()
        self._ensure_io_files()
        self._start_input_poll()

    def _on_close(self) -> None:
        """
        Clear IO files on exit, per spec, then close the UI.
        """
        try:
            self._clear_io_files()
        except Exception:
            # Avoid blocking shutdown due to IO issues.
            pass
        self.root.destroy()

    def _clear_io_files(self) -> None:
        for p in (self.input_path, self.output_path):
            try:
                with open(p, "wb") as f:
                    f.write(b"")
            except FileNotFoundError:
                # If deleted, recreate as empty.
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(b"")
        self._last_input_sig = None

    def _ensure_io_files(self) -> None:
        # Ensure both files exist so other scripts can write to them.
        for p in (self.input_path, self.output_path):
            if not os.path.exists(p):
                with open(p, "wb") as f:
                    f.write(b"")

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container = tk.Frame(self.root, padx=16, pady=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        # Image area
        self.image_frame = tk.LabelFrame(container, text="Image", padx=10, pady=10)
        self.image_frame.grid(row=0, column=0, sticky="nsew")
        self.image_frame.columnconfigure(0, weight=1)
        self.image_frame.rowconfigure(0, weight=1)

        self.image_label = tk.Label(
            self.image_frame,
            text="No image selected.\nClick Upload to choose an image file.",
            anchor="center",
            justify="center",
        )
        self.image_label.grid(row=0, column=0, sticky="nsew")

        # Re-render the current image when the frame is resized / realized.
        self.image_frame.bind("<Configure>", self._on_image_frame_configure)

        # Buttons
        controls = tk.Frame(container, pady=12)
        controls.grid(row=1, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)

        self.upload_button = tk.Button(controls, text="Upload", width=16, command=self._on_upload_clicked)
        self.upload_button.grid(row=0, column=0, sticky="w")

        self.send_button = tk.Button(controls, text="Send", width=16, command=self._on_send_clicked)
        self.send_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

        # Simple status line (helps debug whether an image actually loaded).
        self.status_var = tk.StringVar(value="Ready.")
        status = tk.Label(container, textvariable=self.status_var, anchor="w")
        status.grid(row=2, column=0, sticky="ew")

    def _on_upload_clicked(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return

        try:
            # Per spec: uploading a new image should NOT display it directly.
            # It should only write bytes into `input` (truncate first). The poller
            # is the ONLY thing that updates the image display.
            self.set_image(file_path)
            self.status_var.set(f"Wrote {os.path.basename(self.input_path)} from upload ({os.path.getsize(self.input_path)} bytes)")
        except Exception as e:
            messagebox.showerror("Unable to load image", f"{e}")

    def _on_send_clicked(self) -> None:
        """
        Stub hook for future wiring.
        Replace `on_send` when constructing this class, or edit this method.
        """
        # Always write the current image bytes to the output file (binary), per spec.
        try:
            self._write_output_file()
        except Exception as e:
            messagebox.showerror("Send failed", f"{e}")
            return

        # Optional extra callback for future wiring (laser TX, etc).
        if self._on_send is not None:
            self._on_send()

        self.status_var.set(f"Wrote {os.path.basename(self.output_path)} ({os.path.getsize(self.output_path)} bytes)")

    def set_image(self, file_path: str) -> None:
        """
        Write an image into the `input` file (binary).

        This function is intended to be called:
        - by the Upload button after selecting a local image
        - by other scripts/modules in the future
        """
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # IMPORTANT: Do NOT render the image directly here.
        # The image display should only ever reflect the contents of `input`.
        # We therefore just copy bytes into `input` and let the poller decode+render.
        with open(file_path, "rb") as f:
            data = f.read()
        self._write_input_file(data)

    def set_image_bytes(self, image_bytes: bytes, *, name: str = "input") -> None:
        """
        Display an image from raw bytes (intended for `input` file contents).
        """
        if not image_bytes:
            return

        try:
            from PIL import Image, ImageOps  # type: ignore
        except ModuleNotFoundError as e:
            raise RuntimeError("Pillow is required to decode image bytes.") from e

        self._image_path = None
        self._image_bytes = image_bytes
        img = Image.open(io.BytesIO(image_bytes))
        self._pil_image = ImageOps.exif_transpose(img)
        self._render_image()
        try:
            w, h = self._pil_image.size
            self.status_var.set(f"Loaded from {name} ({w}x{h})")
        except Exception:
            self.status_var.set(f"Loaded from {name}")

    def _on_image_frame_configure(self, _event) -> None:
        # Throttle re-rendering during rapid resizes.
        if self._render_after_id is not None:
            try:
                self.root.after_cancel(self._render_after_id)
            except Exception:
                pass
        self._render_after_id = self.root.after(50, self._render_image)

    def _render_image(self) -> None:
        """
        Render the currently loaded PIL image into the label, sized to the UI.
        """
        if self._pil_image is None:
            return

        # Ensure geometry is up to date; early in the UI lifecycle sizes can be 1x1.
        self.root.update_idletasks()

        target_w = self.image_label.winfo_width()
        target_h = self.image_label.winfo_height()

        # If we haven't been laid out yet, retry shortly.
        if target_w <= 2 or target_h <= 2:
            self._render_after_id = self.root.after(50, self._render_image)
            return

        from PIL import ImageTk  # type: ignore

        img = self._pil_image.copy()
        # Some PIL images are lazy-loaded; ensure pixel data is ready.
        try:
            img.load()
        except Exception:
            pass

        img.thumbnail((target_w, target_h))
        self._tk_image = ImageTk.PhotoImage(img)
        self.image_label.configure(image=self._tk_image, text="")

    def _show_loading_placeholder(self) -> None:
        """
        Show a temporary loading message while `input` is still being written and
        does not yet contain a full valid image.
        """
        self._tk_image = None
        self._pil_image = None
        self.image_label.configure(
            image="",
            text="Loading image from input...\n(Waiting for complete data.)",
        )
        self.status_var.set("Loading image from input (incomplete data).")

    def _clear_input_file(self) -> None:
        with open(self.input_path, "wb") as f:
            f.write(b"")
        # Reset signature so future writes are detected.
        self._last_input_sig = None

    def _write_input_file(self, image_bytes: bytes) -> None:
        # Per spec: overwrite/clear first, then write bytes.
        self._clear_input_file()
        with open(self.input_path, "wb") as f:
            f.write(image_bytes or b"")

    def _write_output_file(self) -> None:
        if not self._image_bytes:
            raise RuntimeError("No image loaded yet.")
        with open(self.output_path, "wb") as f:
            f.write(self._image_bytes)

    def _start_input_poll(self) -> None:
        self.root.after(self.poll_input_ms, self._poll_input_file)

    def _poll_input_file(self) -> None:
        """
        Poll `input` for binary image data. If non-empty and changed, decode & display.
        """
        try:
            st = os.stat(self.input_path)
            sig = (st.st_mtime_ns, st.st_size)

            if st.st_size > 0 and sig != self._last_input_sig:
                with open(self.input_path, "rb") as f:
                    data = f.read()
                if data:
                    try:
                        self.set_image_bytes(data, name=os.path.basename(self.input_path))
                    except Exception:
                        # Most likely the file is still being written and doesn't yet
                        # contain a full valid image. Show a loading placeholder and
                        # wait for the next change.
                        self._show_loading_placeholder()
                self._last_input_sig = sig
            elif st.st_size == 0:
                self._last_input_sig = sig
        except FileNotFoundError:
            # Recreate if deleted.
            self._ensure_io_files()
        except Exception as e:
            # Don’t spam popups; just update status.
            self.status_var.set(f"Input read error: {e}")
        finally:
            self.root.after(self.poll_input_ms, self._poll_input_file)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = LaserTransceiverFrontend()
    app.run()


if __name__ == "__main__":
    main()

