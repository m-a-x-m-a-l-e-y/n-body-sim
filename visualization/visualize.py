#!/usr/bin/env python3

import argparse
import glob
import os
import re
import sys

import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy

MAJOR_BODIES = [
    ("Sun",  (1.0, 0.8, 0.2), 2.5, 18),
    ("Moon", (0.8, 0.8, 0.8), 1.5, 8),
    ("Earth", (0.3, 0.6, 1.0), 2.0, 12),
]

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


def _natural_key(path):
    name = os.path.basename(path)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def list_step_files(directory, pattern):
    files = [f for f in glob.glob(os.path.join(directory, pattern)) if os.path.isfile(f)]
    return sorted(files, key=_natural_key)


def read_step(path):
    rows = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                rows.append([float(v) for v in parts[:3]])
            except ValueError:
                continue
    return np.asarray(rows, dtype=np.float64).reshape(-1, 3)


def load_steps(directory, pattern, stride):
    files = list_step_files(directory, pattern)[::stride]
    if not files:
        sys.exit(f"No step files found in {directory!r} matching {pattern!r}")

    steps, n_bodies = [], None
    for path in files:
        pts = read_step(path)
        if len(pts) == 0:
            continue
        if n_bodies is None:
            n_bodies = len(pts)
        elif len(pts) != n_bodies:
            print(f"warning: {path} has {len(pts)} bodies, expected {n_bodies}; "
                  "missing bodies hold their last position, extras are ignored",
                  file=sys.stderr)
            if len(pts) < n_bodies:
                pts = np.vstack([pts, steps[-1][len(pts):]])
            else:
                pts = pts[:n_bodies]
        steps.append(pts)

    if not steps:
        sys.exit(f"All step files in {directory!r} were empty")
    return np.stack(steps), len(steps)


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
    def __init__(self, P, renderer, color=None, colors=None,
                 line_width=1.0, pixels=5, opacity=1.0):
        self.P = np.ascontiguousarray(P, dtype=np.float64)
        self.B, self.T = self.P.shape[:2]

        self.trail = vtk.vtkPolyData()
        self.trail.SetPoints(vtk.vtkPoints())
        self.trail.SetLines(vtk.vtkCellArray())

        self.head = vtk.vtkPolyData()
        self.head.SetPoints(vtk.vtkPoints())
        verts = vtk.vtkCellArray()
        verts.SetData(_id_array(np.arange(self.B + 1)), _id_array(np.arange(self.B)))
        self.head.SetVerts(verts)

        if colors is not None:
            rgb = np.array([colors[b % len(colors)] for b in range(self.B)]) * 255
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
    ap = argparse.ArgumentParser(
        description="Animate N-body output from a directory of timestep files. "
                    "Each file is one timestep with one 'x y z' line per body: "
                    "line 1 is the Sun, line 2 is the Moon, line 3 is the Earth, "
                    "the rest are passive bodies.")
    ap.add_argument("directory", nargs="?",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "steps"),
                    help="directory of timestep files (default: steps/ next to this script)")
    ap.add_argument("--pattern", default="*",
                    help="glob for step files inside the directory (default '*')")
    ap.add_argument("--seconds", type=float, default=20.0,
                    help="length of one pass through the data (default 20)")
    ap.add_argument("--fps", type=float, default=30.0, help="frames per second (default 30)")
    ap.add_argument("--speed", type=int, default=None,
                    help="time steps advanced per frame (overrides --seconds)")
    ap.add_argument("--trail", type=int, default=0,
                    help="trail length in time steps; 0 = full path so far (default 0)")
    ap.add_argument("--stride", type=int, default=1, help="use only every Nth step file")
    ap.add_argument("--gif", default=None, help="render offscreen and save a GIF")
    ap.add_argument("--frames", type=int, default=300, help="frames in the GIF (default 300)")
    ap.add_argument("--size", type=parse_size, default=None,
                    help="window / GIF size WxH (default 1000x800 live, 800x640 GIF)")
    ap.add_argument("--no-loop", action="store_true",
                    help="stop at the last step instead of starting over")
    args = ap.parse_args()

    if not os.path.isdir(args.directory):
        sys.exit(f"Not a directory: {args.directory}")

    data, n_steps = load_steps(args.directory, args.pattern, max(1, args.stride))
    per_body = data.transpose(1, 0, 2)
    n_major = min(len(MAJOR_BODIES), len(per_body))
    major = [(MAJOR_BODIES[i], per_body[i]) for i in range(n_major)]
    passive = per_body[n_major:]

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.05, 0.05, 0.1)

    groups = []
    if len(passive):
        groups.append(BodyGroup(passive, renderer, colors=PASSIVE_COLORS,
                                line_width=PASSIVE_LINE_WIDTH,
                                pixels=PASSIVE_MARKER_PIXELS, opacity=PASSIVE_OPACITY))
    for (name, color, width, pixels), pts in major:
        groups.append(BodyGroup(pts[None], renderer, color=color,
                                line_width=width, pixels=pixels))

    y = 0.95
    for (name, color, _, _), _ in major:
        key = vtk.vtkTextActor()
        key.SetInput(f"● {name}")
        key.GetTextProperty().SetFontSize(18)
        key.GetTextProperty().SetColor(color)
        key.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        key.SetPosition(0.01, y)
        renderer.AddViewProp(key)
        y -= 0.04

    status = vtk.vtkTextActor()
    status.GetTextProperty().SetFontSize(16)
    status.GetTextProperty().SetColor(1, 1, 1)
    status.SetPosition(10, 10)
    renderer.AddViewProp(status)
    passive_note = f"   |   {len(passive)} other bodies" if len(passive) else ""
    hint = "" if args.gif else "\nspace: pause   +/-: speed   arrows: step"

    def show(frame):
        for g in groups:
            g.update(frame, args.trail)
        status.SetInput(f"step {min(frame, n_steps - 1) + 1} / {n_steps}{passive_note}{hint}")

    window = vtk.vtkRenderWindow()
    window.AddRenderer(renderer)
    window.SetSize(*(args.size or ((800, 640) if args.gif else (1000, 800))))
    window.SetWindowName("Sun / Moon / Earth + other bodies")

    all_pts = data.reshape(-1, 3)
    lo, hi = all_pts.min(axis=0), all_pts.max(axis=0)
    bounds = [lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]]
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

    duration = max(20, int(round(1000 / args.fps)))
    images[0].save(args.gif, save_all=True, append_images=images[1:],
                   duration=duration, loop=0)


if __name__ == "__main__":
    main()