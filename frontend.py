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
        window_size: tuple[int, int] = (900, 600),
    ) -> None:
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{window_size[0]}x{window_size[1]}")

        # Optional callback invoked when "Send" is pressed.
        self._on_send = on_send

        # Keep a reference to the active image object to prevent garbage collection.
        self._tk_image = None
        self._pil_image = None  # original PIL image (if loaded)
        self._image_path: Optional[str] = None
        self._render_after_id: Optional[str] = None

        self._build_ui()

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
            self.set_image(file_path)
        except Exception as e:
            messagebox.showerror("Unable to load image", f"{e}")

    def _on_send_clicked(self) -> None:
        """
        Stub hook for future wiring.
        Replace `on_send` when constructing this class, or edit this method.
        """
        if self._on_send is not None:
            self._on_send()
            return

        # Default behavior for now: a no-op with a simple notification.
        messagebox.showinfo("Send", "Send clicked (stub). Hook this up to your transmit logic later.")

    def set_image(self, file_path: str) -> None:
        """
        Display an image in the UI.

        This function is intended to be called:
        - by the Upload button after selecting a local image
        - by other scripts/modules in the future
        """
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Prefer Pillow for reliable cross-platform image decoding (JPG/PNG/WebP/etc).
        try:
            from PIL import Image, ImageOps, ImageTk  # type: ignore

            self._image_path = file_path
            # Auto-orient based on EXIF (common for phone photos that appear rotated).
            self._pil_image = ImageOps.exif_transpose(Image.open(file_path))
            self._render_image()  # will size to the current widget dimensions
            try:
                w, h = self._pil_image.size
                self.status_var.set(f"Loaded: {os.path.basename(file_path)} ({w}x{h})")
            except Exception:
                self.status_var.set(f"Loaded: {os.path.basename(file_path)}")
            return
        except ModuleNotFoundError:
            # Without Pillow, tkinter's PhotoImage support varies by platform/Tk version.
            # Many installs (including macOS Tk 8.5) cannot display JPG or PNG reliably.
            raise RuntimeError(
                "This UI requires Pillow to display most common image formats (JPG/PNG/WebP).\n\n"
                "Install it with one of:\n"
                "  - python3 -m pip install pillow\n"
                "  - (Raspberry Pi / Debian) sudo apt-get install -y python3-pil python3-pil.imagetk\n\n"
                "Or use a GIF/PPM/PGM image that tkinter can load without Pillow."
            )

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

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = LaserTransceiverFrontend()
    app.run()


if __name__ == "__main__":
    main()

