"""Renderiza piezas en su orientación de impresión (VTK fuera de pantalla).
Gris: pieza · azul: apoyo en la cama · rojo: cara hacia abajo a más de 45° (pide soporte o puente) · naranja: soporte integrado.

  .venv/bin/python herramientas/render_cama.py carpeta [pieza ...]   → carpeta/<pieza>.png y carpeta/hoja.png
"""
import math, os, sys
import numpy as np, trimesh, vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imprimibilidad import CFG
from bandejas import pieza_en_cama


def _actor(t, colores):
    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(t.vertices.astype(np.float64), deep=True))
    cells = np.hstack([np.full((len(t.faces), 1), 3), t.faces]).astype(np.int64).ravel()
    ca = vtk.vtkCellArray(); ca.SetCells(len(t.faces), numpy_to_vtkIdTypeArray(cells, deep=True))
    pd = vtk.vtkPolyData(); pd.SetPoints(pts); pd.SetPolys(ca)
    arr = numpy_to_vtk(colores, deep=True); arr.SetName("c"); pd.GetCellData().SetScalars(arr)
    m = vtk.vtkPolyDataMapper(); m.SetInputData(pd); a = vtk.vtkActor(); a.SetMapper(m)
    return a


def render(nombre, salida, az=-35, el=28, tam=(640, 480)):
    t, sp, _ = pieza_en_cama(nombre)
    ang = CFG[nombre].get("angulo_max", 45.0)
    n = t.face_normals; zmin = t.triangles[:, :, 2].min(1)
    col = np.tile([205, 205, 210], (len(n), 1)).astype(np.uint8)
    col[(n[:, 2] < -math.sin(math.radians(90 - ang))) & (zmin > 0.05)] = [215, 45, 40]
    col[(zmin < 0.05) & (n[:, 2] < -0.999)] = [40, 110, 215]
    r = vtk.vtkRenderer(); r.SetBackground(1, 1, 1); r.AddActor(_actor(t, col))
    if sp is not None:
        r.AddActor(_actor(sp, np.tile([240, 150, 30], (len(sp.faces), 1)).astype(np.uint8)))
    ex = t.extents; s = max(ex[0], ex[1]) * 0.6 + 10
    pl = vtk.vtkPlaneSource(); pl.SetOrigin(-s, -s, -0.2); pl.SetPoint1(s, -s, -0.2); pl.SetPoint2(-s, s, -0.2)
    pl.SetResolution(int(2 * s / 10), int(2 * s / 10))
    pm = vtk.vtkPolyDataMapper(); pm.SetInputConnection(pl.GetOutputPort()); pa = vtk.vtkActor(); pa.SetMapper(pm)
    pa.GetProperty().SetRepresentationToWireframe(); pa.GetProperty().SetColor(.65, .65, .65); r.AddActor(pa)
    tx = vtk.vtkTextActor(); tx.SetInput(f"{nombre}   {ex[0]:.0f} x {ex[1]:.0f} x {ex[2]:.0f} mm")
    tx.GetTextProperty().SetFontSize(17); tx.GetTextProperty().SetColor(0, 0, 0); r.AddViewProp(tx)
    w = vtk.vtkRenderWindow(); w.SetOffScreenRendering(1); w.AddRenderer(r); w.SetSize(*tam)
    cam = r.GetActiveCamera(); d = 3 * max(ex)
    cam.SetFocalPoint(0, 0, ex[2] / 3)
    cam.SetPosition(d * math.cos(math.radians(el)) * math.sin(math.radians(az)),
                    -d * math.cos(math.radians(el)) * math.cos(math.radians(az)), ex[2] / 3 + d * math.sin(math.radians(el)))
    cam.SetViewUp(0, 0, 1); r.ResetCamera(); cam.Zoom(1.25)
    w.Render(); f = vtk.vtkWindowToImageFilter(); f.SetInput(w); f.Update()
    wr = vtk.vtkPNGWriter(); wr.SetFileName(salida); wr.SetInputConnection(f.GetOutputPort()); wr.Write()


def hoja(carpeta, nombres, cols=4, tam=(640, 480)):
    from PIL import Image
    filas = (len(nombres) + cols - 1) // cols
    im = Image.new("RGB", (tam[0] * cols, tam[1] * filas), "white")
    for i, n in enumerate(nombres):
        im.paste(Image.open(os.path.join(carpeta, f"{n}.png")), ((i % cols) * tam[0], (i // cols) * tam[1]))
    im.save(os.path.join(carpeta, "hoja.png"))


if __name__ == "__main__":
    od = sys.argv[1]; os.makedirs(od, exist_ok=True)
    nombres = sys.argv[2:] or [k for k in CFG if not k.startswith("_")]
    for n in nombres:
        render(n, os.path.join(od, f"{n}.png"))
    hoja(od, nombres)
