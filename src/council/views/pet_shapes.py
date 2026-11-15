"""The pet's shapes: the approved design's SVG paths on a 100 x 100 view box, sampled into polygons and lines for a
tkinter canvas, one set per pose."""
from __future__ import annotations

import math
import re
from typing import Any, List, Tuple

Point = Tuple[float, float]
Shape = Tuple[List[Point], bool]      # its points, and whether it is closed

# The design's colours: a coral body with a cream outline and face, a green stem and leaf. On review, the
# first design's brown face lines and the needing-you pupils were dropped: the cream outline is enough.
CORAL, CREAM, STEM, MOUTH = "#D85A30", "#FAECE7", "#639922", "#4A1B0C"
LEAF, BLUE, WHITE, SOFT = "#97C459", "#378ADD", "#FFFFFF", "#888780"
AMBER, PURPLE, TEAL = "#EF9F27", "#7F77DD", "#1D9E75"

BODY = ("M20 84 V50 A30 30 0 0 1 80 50 V84 q-5 8 -10 0 q-5 8 -10 0 q-5 8 -10 0 q-5 8 -10 0 q-5 8 -10 0 "
        "q-5 8 -10 0 Z")
BASE = [
    ("path", "M50 21 q-3 -8 4 -13", {"stroke": STEM, "width": 4}),
    ("ellipse", (60, 11, 6, 3, -25), {"fill": LEAF}),
    ("path", BODY, {"fill": CORAL}),
    ("path", BODY, {"stroke": CREAM, "width": 2, "shrink": (50, 58, 0.86)}),
]


def _nose(y: float) -> tuple[str, str, dict[str, Any]]:
    return ("path", "M48 {0} L52 {0} L50 {1} Z".format(y, y + 3), {"fill": CREAM})


FACES = {
    "asleep": [("path", "M31 52 q7 5 14 0 M55 52 q7 5 14 0", {"stroke": CREAM, "width": 2.5}), _nose(60),
               ("path", "M42 70 q4 3 8 0 q4 -3 8 0", {"stroke": CREAM, "width": 2.5}),
               ("text", (80, 26, "z", 13, "start"), {"fill": SOFT}),
               ("text", (88, 16, "z", 11, "start"), {"fill": SOFT})],
    "working": [("path", "M31 49 h14 a7 7 0 0 1 -14 0 Z M55 49 h14 a7 7 0 0 1 -14 0 Z", {"fill": CREAM}), _nose(60),
                ("path", "M38 69 l4 4 l4 -4 l4 4 l4 -4 l4 4 l4 -4", {"stroke": CREAM, "width": 2.5})],
    "needs-you": [("circle", (38, 50, 7.5), {"fill": CREAM}), ("circle", (62, 50, 7.5), {"fill": CREAM}), _nose(61),
                  ("ellipse", (50, 72, 3.5, 4.5, 0), {"fill": MOUTH, "stroke": CREAM, "width": 2}),
                  ("circle", (14, 18, 10), {"fill": BLUE}),
                  ("text", (14, 23, "?", 14, "middle"), {"fill": WHITE, "bold": True})],
    "stopped": [("path", "M30 45 L46 52 Q44 60 37 60 Q29 58 30 45 Z M70 45 L54 52 Q56 60 63 60 Q71 58 70 45 Z",
                 {"fill": CREAM}), _nose(62),
                ("path", "M34 76 l5 -6 l5 6 l6 -8 l6 8 l5 -6 l5 6", {"stroke": CREAM, "width": 2.5})],
    "done": [("path", "M31 54 q7 -8 14 0 M55 54 q7 -8 14 0", {"stroke": CREAM, "width": 2.5}), _nose(59),
             ("path", "M30 66 l5 7 l5 -5 l5 7 l5 -7 l5 7 l5 -7 l5 5 l5 -7", {"stroke": CREAM, "width": 2.5}),
             ("circle", (12, 22, 3), {"fill": AMBER}), ("circle", (88, 18, 3), {"fill": PURPLE}),
             ("circle", (92, 40, 2.5), {"fill": AMBER}), ("circle", (8, 44, 2.5), {"fill": TEAL}),
             ("circle", (22, 8, 2), {"fill": PURPLE})],
}
NUMBER = r"[-+]?(?:[0-9]*\.[0-9]+|[0-9]+\.?)(?:[eE][-+]?[0-9]+)?"
ARGUMENTS = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "A": 7}    # the numbers each path command takes


def _quad(p0: Point, p1: Point, p2: Point, steps: int = 10) -> list[Point]:
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (k / float(steps) for k in range(1, steps + 1))]


def _arc(p0: Point, rx: float, ry: float, angle: float, large: float, sweep: float, p1: Point,
         step: float = 7.5) -> list[Point]:
    """An SVG arc (endpoint form) as points, by the SVG spec's centre conversion."""
    (x1, y1), (x2, y2) = p0, p1
    if rx == 0 or ry == 0 or (x1, y1) == (x2, y2):
        return [p1]
    phi = math.radians(angle)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    xp, yp = cos_p * dx + sin_p * dy, -sin_p * dx + cos_p * dy
    rx, ry = abs(rx), abs(ry)
    grow = (xp * xp) / (rx * rx) + (yp * yp) / (ry * ry)
    if grow > 1:
        rx, ry = rx * math.sqrt(grow), ry * math.sqrt(grow)
    top = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    bottom = rx * rx * yp * yp + ry * ry * xp * xp
    coef = math.sqrt(max(0.0, top / bottom)) if bottom else 0.0
    if bool(large) == bool(sweep):
        coef = -coef
    cxp, cyp = coef * rx * yp / ry, -coef * ry * xp / rx
    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2.0

    def angle_of(ux: float, uy: float, vx: float, vy: float) -> float:
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    start = angle_of(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    turn = angle_of((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and turn > 0:
        turn -= 2 * math.pi
    elif sweep and turn < 0:
        turn += 2 * math.pi
    steps = max(2, int(math.ceil(abs(math.degrees(turn)) / step)))
    points = []
    for k in range(1, steps + 1):
        t = start + turn * k / steps
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        points.append((cos_p * ex - sin_p * ey + cx, sin_p * ex + cos_p * ey + cy))
    return points


def path_points(d: str) -> list[Shape]:
    """SVG path data as [(points, closed)]: M L H V Q A Z and their relative forms, repeats included."""
    tokens = re.findall(r"[MmLlHhVvQqAaZz]|" + NUMBER, d)
    shapes: list[Shape] = []
    points: list[Point] = []
    x = y = sx = sy = 0.0
    i, command = 0, ""
    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            command = tokens[i]
            i += 1
        elif not command:
            raise ValueError("path data starts without a command: " + d)
        op, rel = command.upper(), command.islower()
        if op == "Z":
            if points:
                shapes.append((points, True))
            points, (x, y) = [], (sx, sy)
            continue
        if op != "M" and not points:
            points = [(x, y)]
        chunk = tokens[i:i + ARGUMENTS[op]]
        if len(chunk) != ARGUMENTS[op] or any(re.match(r"[A-Za-z]", v) for v in chunk):
            raise ValueError("path data ends early: " + d)
        i += ARGUMENTS[op]
        values = [float(v) for v in chunk]
        if op != "M":
            x, y = _drawn(op, rel, values, (x, y), points)
            continue
        nx, ny = (values[0] + x, values[1] + y) if rel else (values[0], values[1])
        if len(points) > 1:
            shapes.append((points, False))
        points, (x, y), (sx, sy) = [(nx, ny)], (nx, ny), (nx, ny)
        command = "l" if rel else "L"            # coordinates after a move are lines
    if len(points) > 1:
        shapes.append((points, False))
    return shapes


def _drawn(op: str, rel: bool, values: list[float], at: Point, points: list[Point]) -> Point:
    """One L, H, V, Q or A command's points added to the shape; where the pen ends."""
    x, y = at
    if op == "L":
        x, y = (values[0] + x, values[1] + y) if rel else (values[0], values[1])
        points.append((x, y))
    elif op == "H":
        x = values[0] + x if rel else values[0]
        points.append((x, y))
    elif op == "V":
        y = values[0] + y if rel else values[0]
        points.append((x, y))
    elif op == "Q":
        cx, cy, nx, ny = values
        if rel:
            cx, cy, nx, ny = cx + x, cy + y, nx + x, ny + y
        points.extend(_quad((x, y), (cx, cy), (nx, ny)))
        x, y = nx, ny
    else:
        rx, ry, angle, large, sweep, nx, ny = values
        if rel:
            nx, ny = nx + x, ny + y
        points.extend(_arc((x, y), rx, ry, angle, large, sweep, (nx, ny)))
        x, y = nx, ny
    return x, y


def _ellipse(cx: float, cy: float, rx: float, ry: float, angle: float, steps: int = 28) -> list[Point]:
    a = math.radians(angle)
    return [(cx + rx * math.cos(t) * math.cos(a) - ry * math.sin(t) * math.sin(a),
             cy + rx * math.cos(t) * math.sin(a) + ry * math.sin(t) * math.cos(a))
            for t in (2 * math.pi * k / steps for k in range(steps))]


def shapes(pose: str) -> list[tuple[Any, ...]]:
    """A pose as drawing steps in view-box units, back to front:
    ("polygon", points, fill, outline, width) · ("line", points, colour, width) · ("oval", (cx, cy, r), fill) ·
    ("text", (x, y), text, size, colour, bold, anchor) — x, y the text's baseline, as in SVG."""
    steps: list[tuple[Any, ...]] = []
    for kind, spec, style in BASE + FACES[pose]:
        if kind == "path":
            cx, cy, k = style.get("shrink", (0, 0, 1.0))
            for points, closed in path_points(spec):
                points = [(cx + k * (px - cx), cy + k * (py - cy)) for px, py in points]
                if "fill" in style and closed:
                    steps.append(("polygon", points, style["fill"], None, 0))
                elif "stroke" in style:
                    width = style["width"] * k
                    steps.append(("polygon", points, None, style["stroke"], width) if closed
                                 else ("line", points, style["stroke"], width))
        elif kind == "ellipse":
            steps.append(("polygon", _ellipse(*spec), style["fill"], style.get("stroke"), style.get("width", 0)))
        elif kind == "circle":
            steps.append(("oval", spec, style["fill"]))
        elif kind == "text":
            x, y, text, size, anchor = spec
            steps.append(("text", (x, y), text, size, style["fill"], bool(style.get("bold")), anchor))
    return steps
