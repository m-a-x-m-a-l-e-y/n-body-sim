#!/usr/bin/env python3
"""
Visualize N-body trajectory files (one "x y z" point per line) in a VTK window.

Usage:
  python visualize.py earth_vtk_data.txt
  python visualize.py sun_vtk_data.txt earth_vtk_data.txt

Requires:  pip install vtk
Mouse: left-drag rotate, right-drag / scroll zoom, middle-drag pan, 'r' reset view.
"""

import sys
import vtk

COLORS = [
    (1.0, 0.8, 0.2),   # yellow
    (0.3, 0.6, 1.0),   # blue
    (0.8, 0.8, 0.8),   # grey
    (1.0, 0.4, 0.4),   # red
    (0.4, 1.0, 0.5),   # green
]


def read_points(path):
    pts = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                pts.append(tuple(float(v) for v in parts[:3]))
            except ValueError:
                continue
    return pts


def trajectory_actor(pts, color):
    """Polyline through all points."""
    points = vtk.vtkPoints()
    points.SetDataTypeToDouble()
    for p in pts:
        points.InsertNextPoint(p)

    line = vtk.vtkPolyLine()
    line.GetPointIds().SetNumberOfIds(len(pts))
    for i in range(len(pts)):
        line.GetPointIds().SetId(i, i)

    cells = vtk.vtkCellArray()
    cells.InsertNextCell(line)

    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetLines(cells)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(color)
    actor.GetProperty().SetLineWidth(2)
    return actor


def marker_actor(pos, color, pixels=14):
    """Dot marking the body's final position. Sized in screen pixels, so it
    stays visible without hiding the path, whatever the scale of the scene."""
    points = vtk.vtkPoints()
    points.SetDataTypeToDouble()
    points.InsertNextPoint(pos)

    verts = vtk.vtkCellArray()
    verts.InsertNextCell(1)
    verts.InsertCellPoint(0)

    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetVerts(verts)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(color)
    prop.SetPointSize(pixels)
    prop.SetRenderPointsAsSpheres(True)
    return actor


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    trajectories = []
    for path in sys.argv[1:]:
        pts = read_points(path)
        if pts:
            trajectories.append((path, pts))
        else:
            print(f"{path}: no points found, skipping")

    if not trajectories:
        sys.exit(1)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.05, 0.05, 0.1)

    legend_lines = []
    for i, (path, pts) in enumerate(trajectories):
        color = COLORS[i % len(COLORS)]
        if len(pts) >= 2:
            renderer.AddActor(trajectory_actor(pts, color))
        renderer.AddActor(marker_actor(pts[-1], color))
        legend_lines.append(f"{path}  ({len(pts)} points)")
        print(f"{path}: {len(pts)} points, start {pts[0]}, end {pts[-1]}")

    # Labels in the corner
    text = vtk.vtkTextActor()
    text.SetInput("\n".join(legend_lines))
    text.GetTextProperty().SetFontSize(16)
    text.GetTextProperty().SetColor(1, 1, 1)
    text.SetPosition(10, 10)
    renderer.AddViewProp(text)

    # Axes in the corner so you can tell x / y / z apart
    axes = vtk.vtkAxesActor()

    window = vtk.vtkRenderWindow()
    window.AddRenderer(renderer)
    window.SetSize(1000, 800)
    window.SetWindowName("Trajectories")

    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

    widget = vtk.vtkOrientationMarkerWidget()
    widget.SetOrientationMarker(axes)
    widget.SetInteractor(interactor)
    widget.SetViewport(0.85, 0.0, 1.0, 0.15)
    widget.EnabledOn()
    widget.InteractiveOff()

    # Look down the z axis, since the orbits are in the x-y plane
    renderer.ResetCamera()
    renderer.GetActiveCamera().SetViewUp(0, 1, 0)
    renderer.ResetCameraClippingRange()

    window.Render()
    interactor.Start()


if __name__ == "__main__":
    main()