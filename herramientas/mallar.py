"""STEP (SolidCraft) → STL estanco con OpenCascade + validación B-rep independiente.

El exportador STL de SolidCraft 0.30 deja grietas (uniones en T) en algunas piezas; el
mallado de OCC comparte la discretización de aristas entre caras y sale cerrado.

  .venv/bin/python herramientas/mallar.py [pieza ...]    → cad/stl/<pieza>.stl (sobrescribe)
"""
import os, sys
import numpy as np, trimesh, manifold3d as mf
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leer_step(path):
    r = STEPControl_Reader()
    if r.ReadFile(path) != 1:
        raise RuntimeError(f"no se pudo leer {path}")
    r.TransferRoots()
    return r.OneShape()


def coser(shape, tol=1e-3):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    sw = BRepBuilderAPI_Sewing(tol)
    sw.Add(shape)
    sw.Perform()
    return sw.SewedShape()


def mallar(shape, flecha=0.02, ang=0.2, digitos=5):
    from OCP.BRepTools import BRepTools
    BRepTools.Clean_s(shape)                         # sin esto, la 2.ª variante reutiliza la malla de la 1.ª
    BRepMesh_IncrementalMesh(shape, flecha, False, ang, True)
    V, F, off = [], [], 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face(ex.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(trsf)
                V.append((p.X(), p.Y(), p.Z()))
            rev = face.Orientation().name == "TopAbs_REVERSED"
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                F.append((off + a - 1, off + c - 1, off + b - 1) if rev else (off + a - 1, off + b - 1, off + c - 1))
            off += tri.NbNodes()
        ex.Next()
    t = trimesh.Trimesh(np.array(V), np.array(F), process=False)
    t.merge_vertices(digits_vertex=digitos)
    t.update_faces(t.nondegenerate_faces())          # triángulos degenerados al unir vértices
    t.remove_unreferenced_vertices()
    return t


def procesar(n):
    sp = os.path.join(RAIZ, "cad", "step", f"{n}.step")
    s = leer_step(sp)
    ok = BRepCheck_Analyzer(s).IsValid()
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g)
    estanco = False
    # variantes (malla y unión de vértices) hasta una estanca; coser solo si ninguna lo es
    for forma, flecha, ang, dig in ((s, 0.02, 0.2, 5), (s, 0.02, 0.15, 4), (s, 0.01, 0.1, 4), (coser(s), 0.02, 0.2, 5)):
        t = mallar(forma, flecha, ang, dig)
        M = mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices, np.float32), tri_verts=np.asarray(t.faces, np.uint32)))
        if M.status() == mf.Error.NoError:
            estanco = True
            break
    if estanco:
        t.export(os.path.join(RAIZ, "cad", "stl", f"{n}.stl"))
    return n, ok, g.Mass(), t.volume, estanco


if __name__ == "__main__":
    nombres = sys.argv[1:] or sorted(f[:-5] for f in os.listdir(os.path.join(RAIZ, "cad", "step")) if f.endswith(".step"))
    for n in nombres:
        n, ok, vb, vm, est = procesar(n)
        print(f"{n:24s} B-rep válido: {'sí' if ok else 'NO'}  vol B-rep {vb:10.0f}  vol malla {vm:10.0f}  "
              f"malla estanca: {'sí' if est else 'NO (se conserva el STL anterior)'}")
