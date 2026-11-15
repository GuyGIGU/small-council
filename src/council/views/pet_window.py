"""The pet's window: a borderless, always-on-top tkinter canvas in the screen's lower right that draws the pose and
its one-line bubble, follows the run on a thread, and closes on a right-click's Close or a stop request."""
from __future__ import annotations

import contextlib
import math
import os
import sys
import threading
import time
from argparse import Namespace
from typing import Any

from council.views.pet import POLL_SECONDS, Follower, remove, view
from council.views.pet_shapes import shapes

PET_PIXELS = 150          # the pet's size on screen at 100% display scaling (the design's 100 x 100 box)
TONES = {"neutral": ("#F1EFE8", "#444441"), "accent": ("#E6F1FB", "#0C447C"),
         "warning": ("#FAEEDA", "#633806"), "success": ("#EAF3DE", "#27500A")}
PLAIN_BG = "#F1EFE8"      # where the window can't be see-through
KEY = "#898881"           # Windows' see-through colour: a grey next to the "z"s, so their soft edges stay grey
MOTION = {"asleep": "drift", "needs-you": "hop", "done": "hop"}
DEMO = (("asleep", "No run open", "neutral"), ("working", "2 of 4 seats in · 132k", "neutral"),
        ("needs-you", "Approve the 3-seat plan?", "accent"), ("stopped", "10 of 10 agents used · your go?", "warning"),
        ("done", "Review done · 4 findings confirmed", "success"))


def note(message: str) -> None:
    """A line in the file COUNCIL_PET_LOG names, when set (for checking a real window without looking)."""
    path = os.environ.get("COUNCIL_PET_LOG")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("{} {}\n".format(time.strftime("%H:%M:%S"), message))
        except OSError:
            pass


def show(opts: Namespace, files: dict[str, str], follower: Follower | None) -> None:
    import tkinter as tk
    from tkinter import font as tkfont

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]  # crisp on a scaled screen
        except Exception:  # noqa: BLE001
            pass
    Window(tk, tkfont, opts, files, follower).run()


def _background(root: Any, tk: Any) -> str:
    """The window's see-through colour where the platform has one, else a plain one."""
    if os.name == "nt":
        try:
            root.wm_attributes("-transparentcolor", KEY)
            return KEY
        except tk.TclError:
            pass
    elif sys.platform == "darwin":
        try:
            root.wm_attributes("-transparent", True)
            return "systemTransparent"
        except tk.TclError:
            pass
    return PLAIN_BG


class Window:
    def __init__(self, tk: Any, tkfont: Any, opts: Namespace, files: dict[str, str], follower: Follower | None):
        self.tk, self.opts, self.files, self.follower = tk, opts, files, follower
        root = self.root = tk.Tk()
        root.withdraw()
        root.title("Small Council pet")
        root.overrideredirect(True)
        root.report_callback_exception = lambda *exc: note("callback error: {}".format(exc[1]))
        with contextlib.suppress(tk.TclError):
            root.wm_attributes("-topmost", True)
        background = _background(root, tk)
        root.configure(bg=background)
        ratio = self.ratio = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.family = tkfont.nametofont("TkDefaultFont").actual("family")
        self.scale = PET_PIXELS / 100.0 * ratio        # view-box units to pixels
        self.width = int(round((PET_PIXELS + 114) * ratio))   # the pet, and room for its bubble
        self.top = 8 * self.scale                      # room for a hop
        self.left = (self.width - 100 * self.scale) / 2.0
        self.bubble_font = tkfont.Font(root=root, family=self.family, size=-int(round(13 * ratio)))
        self.pad_x, self.pad_y = 8 * ratio, 4 * ratio
        self.bubble_top = self.top + 95 * self.scale
        self.height = int(round(self.bubble_top + self.bubble_font.metrics("linespace") + 2 * self.pad_y + 4 * ratio))
        self.canvas = tk.Canvas(root, width=self.width, height=self.height, bg=background, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.x = root.winfo_screenwidth() - self.width - int(24 * ratio)
        self.y = root.winfo_screenheight() - self.height - int(72 * ratio)
        root.geometry("{}x{}+{}+{}".format(self.width, self.height, self.x, self.y))
        self.fonts: dict[tuple[float, bool], Any] = {}
        self.tkfont = tkfont
        self.shown = {"pose": None, "bubble": None, "since": time.time(), "dy": 0.0}
        self.closing = threading.Event()
        self.latest, self.guard, self.seen = {"reading": None, "seq": 0}, threading.Lock(), 0
        self.started = time.time()
        self.grab: dict[str, int] = {}

    def at(self, px: float, py: float) -> tuple[float, float]:
        return self.left + px * self.scale, self.top + py * self.scale

    def flat(self, points: list[tuple[float, float]]) -> list[float]:
        return [c for p in points for c in self.at(*p)]

    def text_font(self, size: float, bold: bool) -> Any:
        if (size, bold) not in self.fonts:
            self.fonts[(size, bold)] = self.tkfont.Font(root=self.root, family=self.family,
                                                        size=-max(6, int(round(size * self.scale))),
                                                        weight="bold" if bold else "normal")
        return self.fonts[(size, bold)]

    def draw_pet(self, pose: str) -> None:
        canvas, scale = self.canvas, self.scale
        canvas.delete("pet")
        for step in shapes(pose):
            if step[0] == "polygon":
                _, points, fill, outline, line = step
                canvas.create_polygon(self.flat(points), fill=fill or "", outline=outline or "",
                                      width=line * scale if outline else 0, joinstyle="round", tags="pet")
            elif step[0] == "line":
                _, points, colour, line = step
                canvas.create_line(self.flat(points), fill=colour, width=line * scale, capstyle="round",
                                   joinstyle="round", tags="pet")
            elif step[0] == "oval":
                (cx, cy, r), fill = step[1], step[2]
                x0, y0 = self.at(cx - r, cy - r)
                x1, y1 = self.at(cx + r, cy + r)
                canvas.create_oval(x0, y0, x1, y1, fill=fill, outline="", tags="pet")
            elif step[0] == "text":
                _, (tx, ty), word, size, colour, bold, anchor = step
                face = self.text_font(size, bold)
                px, py = self.at(tx, ty)
                canvas.create_text(px, py + face.metrics("descent"), text=word, fill=colour, font=face,
                                   anchor="s" if anchor == "middle" else "sw", tags="pet")

    def fit(self, text: str, room: float) -> str:
        if self.bubble_font.measure(text) <= room:
            return text
        while text and self.bubble_font.measure(text + "…") > room:
            text = text[:-1]
        return text.rstrip() + "…"

    def draw_bubble(self, text: str, tone: str) -> None:
        canvas, width, ratio = self.canvas, self.width, self.ratio
        canvas.delete("bubble")
        fill, ink = TONES.get(tone, TONES["neutral"])
        text = self.fit(text, width - 2 * self.pad_x - 4 * ratio)
        w = self.bubble_font.measure(text) + 2 * self.pad_x
        h = self.bubble_font.metrics("linespace") + 2 * self.pad_y
        x0, y0, r = (width - w) / 2.0, self.bubble_top, 6 * ratio
        x1, y1 = x0 + w, y0 + h
        canvas.create_polygon([x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
                               x0, y1, x0, y1 - r, x0, y0 + r, x0, y0], smooth=True, fill=fill, outline="#D3D1C7",
                              tags="bubble")
        canvas.create_text(width / 2.0, y0 + h / 2.0, text=text, fill=ink, font=self.bubble_font, tags="bubble")

    def put(self, pose: str, bubble: str, tone: str) -> None:
        if pose != self.shown["pose"]:
            self.shown.update(pose=pose, since=time.time(), dy=0.0)
            self.draw_pet(pose)
            note("pose " + pose)
        if (bubble, tone) != self.shown["bubble"]:
            self.shown["bubble"] = (bubble, tone)
            self.draw_bubble(bubble, tone)

    def close(self, *_: Any) -> None:
        if not self.closing.is_set():
            self.closing.set()
            note("closing")
            self.root.destroy()

    def animate(self) -> None:
        if self.closing.is_set():
            return
        motion, t = MOTION.get(self.shown["pose"]), time.time() - self.shown["since"]
        dy = 0.0
        if motion == "hop":
            dy = -6 * self.scale * (1 - math.cos(2 * math.pi * t / 1.1)) / 2
        elif motion == "drift":
            dy = 3 * self.scale * (1 - math.cos(2 * math.pi * t / 3.0)) / 2
        if abs(dy - self.shown["dy"]) >= 0.25:
            self.canvas.move("pet", 0, dy - self.shown["dy"])
            self.shown["dy"] = dy
        self.root.after(40, self.animate)

    def watch(self) -> None:
        """Read the run every POLL_SECONDS on its own thread; the window shows the latest reading."""
        while not self.closing.is_set():
            try:
                reading = self.follower.read()  # type: ignore[union-attr]
            except Exception as exc:  # noqa: BLE001 — a reading must never take the window down
                reading = {"kind": "error", "note": "Can't read the run right now", "detail": str(exc)}
            if reading.get("detail"):
                note("reading: " + reading["detail"].replace("\n", " ")[:300])
            with self.guard:
                self.latest["reading"], self.latest["seq"] = reading, self.latest["seq"] + 1
            self.closing.wait(POLL_SECONDS)

    def tick(self) -> None:
        if self.closing.is_set():
            return
        if os.path.exists(self.files["stop"]):
            remove(self.files["stop"])
            self.close()
            return
        if self.opts.demo:
            self.put(*DEMO[int((time.time() - self.started) / 2.0) % len(DEMO)])
        elif self.follower is not None:
            with self.guard:
                seq, reading = self.latest["seq"], self.latest["reading"]
            if seq != self.seen:
                self.seen = seq
                self.put(*view(reading))
        self.root.after(250, self.tick)

    def press(self, event: Any) -> None:
        self.grab["dx"], self.grab["dy"] = event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y()

    def drag(self, event: Any) -> None:
        self.root.geometry("+{}+{}".format(event.x_root - self.grab.get("dx", 0),
                                           event.y_root - self.grab.get("dy", 0)))

    def run(self) -> None:
        opts, root, canvas = self.opts, self.root, self.canvas
        if self.follower is not None:
            threading.Thread(target=self.watch, daemon=True).start()
        self.started = time.time()
        if opts.pose:
            self.put(*next(d for d in DEMO if d[0] == opts.pose))
        elif opts.demo:
            self.put(*DEMO[0])
        else:
            self.put("asleep", "Looking for the council run…", "neutral")
        menu = self.tk.Menu(root, tearoff=0)
        menu.add_command(label="Close", command=self.close)

        def popup(event: Any) -> None:
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        canvas.bind("<ButtonPress-1>", self.press)
        canvas.bind("<B1-Motion>", self.drag)
        canvas.bind("<Button-3>", popup)
        if sys.platform == "darwin":
            canvas.bind("<Button-2>", popup)
            canvas.bind("<Control-Button-1>", popup)
        root.deiconify()
        root.update()
        with open(self.files["pid"], "w", encoding="utf-8") as handle:
            handle.write("{}\n".format(os.getpid()))
        note("shown {}x{}+{}+{} viewable={} pid={}".format(self.width, self.height, self.x, self.y,
                                                          root.winfo_viewable(), os.getpid()))
        if opts.exit_after:
            root.after(int(opts.exit_after * 1000), self.close)
        if not opts.still:
            root.after(40, self.animate)
        root.after(250, self.tick)
        root.mainloop()
        self.closing.set()
