"""STL listos para el laminador: cada pieza ya girada a su orientación de impresión y apoyada en z=0, con sus
soportes integrados (si los lleva) en el mismo fichero.

  .venv/bin/python herramientas/bandejas.py [pieza ...]     → imprimir/<pieza>.stl

Soportes integrados:
  - P19/P20 (casquetes superiores): el buje queda sobre el hueco del buje inferior. Un tapón cilíndrico suelto
    (0,4 mm de holgura radial, 1 capa de hueco por arriba) lo sostiene; al despegar la pieza, el tapón se queda
    en la cama.
"""
import json, os, sys
import numpy as np, trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imprimibilidad import CFG, P, RAIZ, matriz_impresion

CQ = P["parpados"]["casquete"]


def soporte(nombre):
    """Soportes integrados de la pieza, en coordenadas de montaje (None si no lleva)."""
    if nombre in ("P19_casquete_sup_der", "P20_casquete_sup_izq"):
        s = 1 if nombre.endswith("der") else -1
        t = CQ["sup"]["tapon_soporte"]
        x0, x1 = CQ["x_base"], CQ["sup"]["x_tope_buje_inf"] - t["hueco_z"]
        c = trimesh.creation.cylinder(radius=t["R"], height=x1 - x0, sections=180)
        c.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], [s, 0, 0]))
        c.apply_translation([s * (x0 + x1) / 2, 0, 0])
        return c
    return None


def pieza_en_cama(nombre):
    t = trimesh.load(os.path.join(RAIZ, "cad", "stl", f"{nombre}.stl"), force="mesh")
    t.merge_vertices()
    M = matriz_impresion(t, CFG[nombre]["arriba"], CFG[nombre].get("giro", 0.0))
    t.apply_transform(M)
    sp = soporte(nombre)
    if sp is not None:
        sp.apply_transform(M)
    return t, sp, M


if __name__ == "__main__":
    nombres = sys.argv[1:] or [k for k in CFG if not k.startswith("_")]
    od = os.path.join(RAIZ, "imprimir"); os.makedirs(od, exist_ok=True)
    for n in nombres:
        t, sp, _ = pieza_en_cama(n)
        todo = trimesh.util.concatenate([t, sp]) if sp is not None else t
        todo.export(os.path.join(od, f"{n}.stl"))
        e = todo.extents
        print(f"{n:24s} {e[0]:6.1f} × {e[1]:6.1f} × {e[2]:6.1f} mm" + ("   + soporte integrado" if sp is not None else ""))
