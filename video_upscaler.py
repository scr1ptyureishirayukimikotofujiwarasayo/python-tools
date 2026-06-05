import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2

RESOLUTIONS = {
    "1440p (2560x1440)": (2560, 1440),
    "4K (3840x2160)": (3840, 2160),
    "4K DCI (4096x2160)": (4096, 2160),
    "8K (7680x4320)": (7680, 4320),
}


class VideoUpscalerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Upscaler")
        self.root.geometry("520x470")
        self.root.resizable(False, False)

        self.input_path = tk.StringVar()
        self.target_res = tk.StringVar(value="4K (3840x2160)")
        self.codec = tk.StringVar(value="mp4v")
        self.use_ffmpeg = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Select a video file to begin.")

        self._cancelled = False
        self._processing = False

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Input Video", font=("", 10, "bold")).pack(anchor="w")
        row1 = ttk.Frame(frame)
        row1.pack(fill="x", pady=(2, 4))
        ttk.Entry(row1, textvariable=self.input_path, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(row1, text="Browse...", command=self._browse).pack(
            side="right", padx=(6, 0)
        )

        ttk.Label(frame, text="Target Resolution", font=("", 10, "bold")).pack(
            anchor="w", pady=(8, 2)
        )
        res_frame = ttk.Frame(frame)
        res_frame.pack(fill="x")
        for i, (label, (w, h)) in enumerate(RESOLUTIONS.items()):
            ttk.Radiobutton(
                res_frame,
                text=label,
                variable=self.target_res,
                value=label,
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16), pady=2)

        custom_frame = ttk.Frame(frame)
        custom_frame.pack(fill="x", pady=(4, 0))
        self.custom_w = tk.StringVar(value="1920")
        self.custom_h = tk.StringVar(value="1080")
        ttk.Radiobutton(
            custom_frame,
            text="Custom:",
            variable=self.target_res,
            value="custom",
        ).pack(side="left")
        ttk.Entry(custom_frame, textvariable=self.custom_w, width=6).pack(side="left", padx=4)
        ttk.Label(custom_frame, text="x").pack(side="left")
        ttk.Entry(custom_frame, textvariable=self.custom_h, width=6).pack(side="left", padx=4)

        ttk.Label(frame, text="Codec", font=("", 10, "bold")).pack(anchor="w", pady=(10, 2))
        codec_frame = ttk.Frame(frame)
        codec_frame.pack(fill="x")
        ttk.Radiobutton(codec_frame, text="mp4v (MP4)", variable=self.codec, value="mp4v").pack(
            side="left", padx=(0, 16)
        )
        ttk.Radiobutton(codec_frame, text="avc1 (H.264)", variable=self.codec, value="avc1").pack(
            side="left", padx=(0, 16)
        )
        ttk.Radiobutton(codec_frame, text="XVID (AVI)", variable=self.codec, value="XVID").pack(side="left")

        ttk.Checkbutton(
            frame,
            text="Prefer FFmpeg (must be installed and on PATH)",
            variable=self.use_ffmpeg,
        ).pack(anchor="w", pady=(6, 0))

        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=(14, 4))
        self.upscale_btn = ttk.Button(
            btn_row, text="Upscale Video", command=self._start_upscale, padding=(12, 6)
        )
        self.upscale_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = ttk.Button(
            btn_row, text="Cancel", command=self._cancel, padding=(12, 6), state="disabled"
        )
        self.cancel_btn.pack(side="left")

        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.pack(fill="x", pady=(4, 0))

        ttk.Label(frame, textvariable=self.status, wraplength=480).pack(
            anchor="w", pady=(8, 0)
        )

    def _set_ui_state(self, processing):
        state = "disabled" if processing else "normal"
        self.upscale_btn.configure(state=state)
        self.cancel_btn.configure(state="normal" if processing else "disabled")

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select a Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mkv *.mov *.webm *.m4v *.wmv *.flv"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.input_path.set(path)

    def _cancel(self):
        self._cancelled = True
        self.status.set("Cancelling...")

    def _on_close(self):
        if self._processing:
            self._cancelled = True
        self.root.destroy()

    def _start_upscale(self):
        src = self.input_path.get().strip()
        if not src:
            messagebox.showwarning("No file", "Please select a video file first.")
            return
        if not os.path.isfile(src):
            messagebox.showerror("Not found", f"File does not exist:\n{src}")
            return

        res_label = self.target_res.get()
        if res_label == "custom":
            try:
                width = int(self.custom_w.get())
                height = int(self.custom_h.get())
            except ValueError:
                messagebox.showerror("Invalid", "Custom width/height must be integers.")
                return
        else:
            width, height = RESOLUTIONS[res_label]

        base, ext = os.path.splitext(src)
        suffix = f"_{width}x{height}"
        dst = f"{base}{suffix}{ext}"
        if os.path.exists(dst):
            if not messagebox.askyesno("Overwrite?", f"Output already exists:\n{dst}\n\nOverwrite?"):
                return

        self._cancelled = False
        self._processing = True
        self._set_ui_state(True)
        self.progress["value"] = 0
        self.status.set(f"Upscaling to {width}x{height} ...")

        t = threading.Thread(
            target=self._upscale_thread,
            args=(src, dst, width, height),
            daemon=True,
        )
        t.start()

    def _upscale_thread(self, src, dst, width, height):
        codec = self.codec.get()
        use_ffmpeg = self.use_ffmpeg.get()

        success = False
        if use_ffmpeg and not self._cancelled:
            try:
                success = self._run_ffmpeg(src, dst, width, height, codec)
                if not success and not self._cancelled:
                    self.root.after(0, self.status.set, "FFmpeg failed. Falling back to OpenCV...")
            except Exception as e:
                self.root.after(0, self.status.set, f"FFmpeg error: {e}")

        if not success and not self._cancelled:
            success = self._upscale_opencv(src, dst, width, height, codec)

        if self._cancelled:
            self.root.after(0, self.status.set, "Cancelled.")
            if os.path.exists(dst):
                try:
                    os.remove(dst)
                except OSError:
                    pass
        elif success:
            self.root.after(0, lambda: self.progress.configure(value=self.progress["maximum"]))
            self.root.after(0, self.status.set, f"Done! Saved to:\n{dst}")
            self.root.after(0, lambda: messagebox.showinfo("Complete", f"Video upscaled successfully.\n\nSaved to:\n{dst}"))
        else:
            self.root.after(0, self.status.set, "Upscaling failed.")
            self.root.after(0, lambda: messagebox.showerror("Failed", "Could not upscale the video."))

        self._processing = False
        self.root.after(0, lambda: self._set_ui_state(False))

    def _run_ffmpeg(self, src, dst, width, height, codec):
        import subprocess

        vcodec = "libx264" if codec == "avc1" else "libxvid"
        cmd = [
            "ffmpeg", "-y",
            "-i", src,
            "-vf", f"scale={width}:{height}:flags=lanczos",
            "-c:v", vcodec,
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "copy",
            dst,
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        for line in proc.stdout:
            if self._cancelled:
                proc.terminate()
                proc.wait()
                return False
            line = line.strip()
            if "time=" in line:
                self.root.after(0, self.status.set, f"FFmpeg: {line}")
        proc.wait()
        return proc.returncode == 0 and os.path.exists(dst)

    def _upscale_opencv(self, src, dst, width, height, codec):
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = 1

        if codec == "mp4v":
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        elif codec == "avc1":
            fourcc = cv2.VideoWriter_fourcc(*"avc1")
        else:
            fourcc = cv2.VideoWriter_fourcc(*"XVID")

        ext = os.path.splitext(dst)[1].lower()
        if ext != ".avi" and codec == "XVID":
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        writer = cv2.VideoWriter(dst, fourcc, fps, (width, height))
        if not writer.isOpened():
            cap.release()
            return False

        self.root.after(0, lambda: self.progress.configure(maximum=total_frames))
        frame_idx = 0

        while True:
            if self._cancelled:
                break
            ret, frame = cap.read()
            if not ret:
                break

            upscaled = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LANCZOS4)
            writer.write(upscaled)
            frame_idx += 1

            if frame_idx % 30 == 0 or frame_idx == total_frames:
                pct = frame_idx / total_frames * 100
                self.root.after(0, self.status.set,
                    f"Processing frame {frame_idx}/{total_frames} ({pct:.1f}%)")
                self.root.after(0, lambda v=frame_idx: self.progress.configure(value=v))

        cap.release()
        writer.release()

        if self._cancelled:
            return False
        return frame_idx > 0


def main():
    root = tk.Tk()
    VideoUpscalerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
