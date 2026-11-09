#!/usr/bin/env python3
"""
Animate N-body trajectory files (one "x y z" point per line, one line per time step).

The first three files are the Sun, Earth and Moon (in that order); every file after
that is drawn as a passive point mass. All files are assumed to share the same time
step, so line i of every file is the same moment in time.

Usage:
  python visualize.py sun.txt earth.txt moon.txt passive_*.txt              # live window
  python visualize.py sun.txt earth.txt moon.txt passive_*.txt --gif orbit.gif

  # Sun, Earth, Moon in their own files + one file of N passive bodies
  # ('x y z' per line: all N bodies of step 0, then step 1, ...)
  python visualize.py sun.txt earth.txt moon.txt nbodies_vtk_data.txt -n 100

  # Everything in one file (its bodies 0-2 are the Sun, Earth, Moon)
  python visualize.py all_bodies.txt -n 103

Options:
  -n, --nbodies N   bodies per time step in each combined file. With several files,
                    the first three are Sun, Earth, Moon and the rest are combined
                    files of N passive bodies; with one file, N counts all bodies
  --body-major      combined file lists all steps of body 0, then body 1, ...
                    (default: all bodies of step 0, then step 1, ...)
  --seconds S   length of one pass through the data (default 20)
  --fps F       frames per second (default 30)
  --speed N     time steps advanced per frame (overrides --seconds)
  --trail N     trail length in time steps; 0 = full path so far (default 0)
  --stride N    keep only every Nth line of each file (saves memory on long runs)
  --gif FILE    render offscreen and save a GIF instead of opening a window
  --frames N    number of frames in the GIF (default 300)
  --size WxH    window / GIF size (default 1000x800 live, 800x640 GIF)
  --no-loop     stop at the last step instead of starting over (live window)

Live window keys:
  space  pause / resume        + / -  faster / slower
  Right / Left  step forward / back while paused
  Mouse: left-drag rotate, right-drag / scroll zoom, middle-drag pan, 'r' reset view.

Requires:  pip install vtk numpy        (and pillow for --gif)
"""

import argparse
import sys

import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy

# (name, color, line width, marker size in pixels) for the first three files
MAJOR_BODIES = [
    ("Sun",   (1.0, 0.8, 0.2), 2.5, 18),
    ("Earth", (0.3, 0.6, 1.0), 2.0, 12),
    ("Moon",  (0.8, 0.8, 0.8), 1.5, 8),
]

# Passive masses cycle through these muted colors, drawn thinner and smaller
PASSIVE_COLORS = [
    (1.0, 0.45, 0.45),
    (0.45, 1.0, 0.55),
    (0.75, 0.5, 1.0),
    (1.0, 0.6, 0.2),
    (0.3, 0.9, 0.9),
    (1.0, 0.5, 0.85),
]
PASSIVE_LINE_WIDTH = 1.0
PASSIVE_MARKER_PIXELS = 5
PASSIVE_OPACITY = 0.7

ID_DTYPE = np.int64 if vtk.vtkIdTypeArray().GetDataTypeSize() == 8 else np.int32


def _read_rows(path):
    """All lines of numbers in a file, as lists of floats (other lines skipped)."""
    rows = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                rows.append([float(v) for v in parts])
            except ValueError:
                continue
    return rows


def read_points(path, stride=1):
    """One body per file: 'x y z' per line, one line per time step."""
    pts = [r[:3] for r in _read_rows(path)]
    return np.asarray(pts, dtype=np.float64)[::stride].reshape(-1, 3)


def read_nbodies(path, n_bodies, stride=1, body_major=False):
    """Many bodies in one file. Returns a list with one (steps, 3) array per body.

    Two layouts are understood:
      * 'x y z' per line, the n_bodies lines of step 0 first, then step 1, ...
        (or every step of body 0 first, then body 1, ... with body_major=True)
      * one line per time step holding all bodies: x0 y0 z0 x1 y1 z1 ...
    """
    rows = _read_rows(path)
    if not rows:
        return []
    width = min(len(r) for r in rows)

    if width >= 6 and width % 3 == 0:
        # One line per step, 3 numbers per body
        n = width // 3
        data = np.asarray([r[:width] for r in rows], dtype=np.float64)
        per_body = data.reshape(len(rows), n, 3).transpose(1, 0, 2)
    else:
        if not n_bodies or n_bodies < 1:
            sys.exit(f"{path}: 3 numbers per line, so pass --nbodies N "
                     "(the number of bodies written each time step)")
        data = np.asarray([r[:3] for r in rows], dtype=np.float64)
        n_steps = len(data) // n_bodies          # drop a half-written last step
        if n_steps == 0:
            sys.exit(f"{path}: fewer than {n_bodies} lines")
        data = data[:n_steps * n_bodies]
        if body_major:
            per_body = data.reshape(n_bodies, n_steps, 3)
        else:
            per_body = data.reshape(n_steps, n_bodies, 3).transpose(1, 0, 2)

    return [np.ascontiguousarray(b[::stride]) for b in per_body]


def _id_array(a):
    return numpy_to_vtkIdTypeArray(np.ascontiguousarray(a, dtype=ID_DTYPE), deep=1)


def _actor(poly, color=None, line_width=None, point_pixels=None, opacity=1.0,
           use_cell_colors=False):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly)
    if use_cell_colors:
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
        mapper.ScalarVisibilityOn()
    else:
        mapper.ScalarVisibilityOff()

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    if color is not None:
        prop.SetColor(color)
    if line_width is not None:
        prop.SetLineWidth(line_width)
    if point_pixels is not None:
        prop.SetPointSize(point_pixels)
        prop.SetRenderPointsAsSpheres(True)
    prop.SetOpacity(opacity)
    return actor


class BodyGroup:
    """A set of bodies drawn with one trail polydata and one marker polydata.
    Each frame the trails and markers are rebuilt from numpy slices, which stays
    fast even with thousands of passive masses."""

    def __init__(self, trajectories, renderer, color=None, colors=None,
                 line_width=1.0, pixels=5, opacity=1.0):
        B = len(trajectories)
        T = max(len(t) for t in trajectories)
        # Pad shorter trajectories by holding their last position
        P = np.empty((B, T, 3))
        for b, t in enumerate(trajectories):
            P[b, :len(t)] = t
            P[b, len(t):] = t[-1]
        self.P, self.B, self.T = P, B, T

        self.trail = vtk.vtkPolyData()
        self.trail.SetPoints(vtk.vtkPoints())
        self.trail.SetLines(vtk.vtkCellArray())

        self.head = vtk.vtkPolyData()
        self.head.SetPoints(vtk.vtkPoints())
        verts = vtk.vtkCellArray()
        verts.SetData(_id_array(np.arange(B + 1)), _id_array(np.arange(B)))
        self.head.SetVerts(verts)

        if colors is not None:
            rgb = np.array([colors[b % len(colors)] for b in range(B)]) * 255
            rgb = np.ascontiguousarray(rgb.astype(np.uint8))
            self.trail.GetCellData().SetScalars(numpy_to_vtk(rgb, deep=1))
            self.head.GetCellData().SetScalars(numpy_to_vtk(rgb, deep=1))

        cell_colors = colors is not None
        renderer.AddActor(_actor(self.trail, color=color, line_width=line_width,
                                 opacity=opacity, use_cell_colors=cell_colors))
        renderer.AddActor(_actor(self.head, color=color, point_pixels=pixels,
                                 use_cell_colors=cell_colors))

    def update(self, frame, trail_len):
        hi = min(frame, self.T - 1)
        lo = 0 if trail_len <= 0 else max(0, hi - trail_len + 1)
        L = hi - lo + 1

        seg = np.ascontiguousarray(self.P[:, lo:hi + 1].reshape(-1, 3))
        self.trail.GetPoints().SetData(numpy_to_vtk(seg, deep=1))
        # One polyline per body: body b uses points b*L .. b*L + L - 1
        self.trail.GetLines().SetData(_id_array(np.arange(0, self.B * L + 1, L)),
                                      _id_array(np.arange(self.B * L)))
        self.trail.Modified()

        heads = np.ascontiguousarray(self.P[:, hi])
        self.head.GetPoints().SetData(numpy_to_vtk(heads, deep=1))
        self.head.Modified()


def parse_size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--speed", type=int, default=None)
    ap.add_argument("--trail", type=int, default=0)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--gif", default=None)
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--size", type=parse_size, default=None)
    ap.add_argument("--no-loop", action="store_true")
    ap.add_argument("-n", "--nbodies", type=int, default=None)
    ap.add_argument("--body-major", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()

    if args.help or not args.files:
        sys.stderr.write(__doc__)
        sys.exit(0 if args.help else 1)

    stride = max(1, args.stride)
    combined = args.nbodies is not None or args.body_major
    if not combined and len(args.files) == 1:
        # A single file with several bodies per line is also a combined file
        rows = _read_rows(args.files[0])
        combined = bool(rows) and min(len(r) for r in rows) >= 6

    # With several files and -n, the first three are the Sun, Earth and Moon
    # (one body each) and every file after them holds N passive bodies.
    # With a single combined file, its first three bodies are the Sun, Earth, Moon.
    n_single = len(MAJOR_BODIES) if (combined and len(args.files) > 1) else 0

    bodies = []
    for i, path in enumerate(args.files):
        if combined and i >= n_single:
            bodies.extend(read_nbodies(path, args.nbodies, stride, args.body_major))
        else:
            bodies.append(read_points(path, stride))
    bodies = [b for b in bodies if len(b) > 0]  # skip empty files silently

    major = []    # (name, pts, color, width, pixels)
    passive = []  # pts
    for idx, pts in enumerate(bodies):
        if idx < len(MAJOR_BODIES):
            name, color, width, pixels = MAJOR_BODIES[idx]
            major.append((name, pts, color, width, pixels))
        else:
            passive.append(pts)

    if not major and not passive:
        sys.exit(1)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.05, 0.05, 0.1)

    groups = []
    # Passive masses first, so the Sun/Earth/Moon draw on top of them
    if passive:
        groups.append(BodyGroup(passive, renderer, colors=PASSIVE_COLORS,
                                line_width=PASSIVE_LINE_WIDTH,
                                pixels=PASSIVE_MARKER_PIXELS, opacity=PASSIVE_OPACITY))
    for name, pts, color, width, pixels in major:
        groups.append(BodyGroup([pts], renderer, color=color,
                                line_width=width, pixels=pixels))

    n_steps = max(g.T for g in groups)

    # Color key for the major bodies, top-left
    y = 0.95
    for name, _, color, _, _ in major:
        key = vtk.vtkTextActor()
        key.SetInput(f"● {name}")
        key.GetTextProperty().SetFontSize(18)
        key.GetTextProperty().SetColor(color)
        key.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        key.SetPosition(0.01, y)
        renderer.AddViewProp(key)
        y -= 0.04

    # Status line, bottom-left
    status = vtk.vtkTextActor()
    status.GetTextProperty().SetFontSize(16)
    status.GetTextProperty().SetColor(1, 1, 1)
    status.SetPosition(10, 10)
    renderer.AddViewProp(status)
    passive_note = f"   |   {len(passive)} passive masses" if passive else ""
    hint = "" if args.gif else "\nspace: pause   +/-: speed   arrows: step"

    def show(frame):
        for g in groups:
            g.update(frame, args.trail)
        status.SetInput(f"step {min(frame, n_steps - 1) + 1} / {n_steps}{passive_note}{hint}")

    window = vtk.vtkRenderWindow()
    window.AddRenderer(renderer)
    window.SetSize(*(args.size or ((800, 640) if args.gif else (1000, 800))))
    window.SetWindowName("Sun / Earth / Moon + passive masses")

    # Frame the camera on the whole run, so the view doesn't jump as trails grow
    all_pts = np.concatenate([g.P.reshape(-1, 3) for g in groups])
    lo, hi = all_pts.min(axis=0), all_pts.max(axis=0)
    bounds = [lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]]
    # Look down the z axis, since the orbits are in the x-y plane
    renderer.GetActiveCamera().SetViewUp(0, 1, 0)
    renderer.ResetCamera(bounds)

    if args.gif:
        render_gif(window, renderer, show, n_steps, args)
    else:
        run_live(window, renderer, show, n_steps, args)


def run_live(window, renderer, show, n_steps, args):
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

    # Axes in the corner so you can tell x / y / z apart
    widget = vtk.vtkOrientationMarkerWidget()
    widget.SetOrientationMarker(vtk.vtkAxesActor())
    widget.SetInteractor(interactor)
    widget.SetViewport(0.85, 0.0, 1.0, 0.15)
    widget.EnabledOn()
    widget.InteractiveOff()

    speed = args.speed or max(1, round(n_steps / (args.fps * args.seconds)))
    state = {"frame": 0, "speed": speed, "paused": False}

    def redraw():
        show(state["frame"])
        renderer.ResetCameraClippingRange()
        window.Render()

    def on_timer(obj, event):
        if state["paused"]:
            return
        nxt = state["frame"] + state["speed"]
        if nxt >= n_steps:
            nxt = n_steps - 1 if args.no_loop else 0
        state["frame"] = nxt
        redraw()

    def on_key(obj, event):
        key = obj.GetKeySym()
        if key == "space":
            state["paused"] = not state["paused"]
        elif key in ("plus", "equal", "KP_Add"):
            state["speed"] *= 2
        elif key in ("minus", "underscore", "KP_Subtract"):
            state["speed"] = max(1, state["speed"] // 2)
        elif key == "Right":
            state["frame"] = min(n_steps - 1, state["frame"] + state["speed"])
            redraw()
        elif key == "Left":
            state["frame"] = max(0, state["frame"] - state["speed"])
            redraw()

    interactor.AddObserver("TimerEvent", on_timer)
    interactor.AddObserver("KeyPressEvent", on_key)

    show(0)
    interactor.Initialize()
    window.Render()
    interactor.CreateRepeatingTimer(max(1, int(1000 / args.fps)))
    interactor.Start()


def render_gif(window, renderer, show, n_steps, args):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("--gif needs Pillow:  pip install pillow")

    window.SetOffScreenRendering(1)
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(window)
    grab.SetInputBufferTypeToRGB()
    grab.ReadFrontBufferOff()

    n_frames = max(1, min(args.frames, n_steps))
    frame_ids = np.unique(np.linspace(0, n_steps - 1, n_frames).round().astype(int))

    images = []
    for f in frame_ids:
        show(int(f))
        renderer.ResetCameraClippingRange()
        window.Render()
        grab.Modified()
        grab.Update()
        img = grab.GetOutput()
        w, h, _ = img.GetDimensions()
        arr = vtk_to_numpy(img.GetPointData().GetScalars()).reshape(h, w, -1)[::-1]
        images.append(Image.fromarray(np.ascontiguousarray(arr[:, :, :3])))

    # GIF timing is in 1/100 s; most viewers clamp anything under 20 ms
    duration = max(20, int(round(1000 / args.fps)))
    images[0].save(args.gif, save_all=True, append_images=images[1:],
                   duration=duration, loop=0)


if __name__ == "__main__":
    main()