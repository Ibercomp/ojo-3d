"""Construye piezas en la app abierta (para verlas en directo) y, en paralelo, en la CLI
headless (STEP + STL + .sc por pieza).

  .venv/bin/python herramientas/construir.py                 # todas
  .venv/bin/python herramientas/construir.py P03_parpado_sup  # algunas
  opciones: --sin-vivo   --sin-cli   --nuevo (empieza un CONJUNTO vacío en la app)
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piezas import PIEZAS
from sc import RAIZ

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = {a for a in sys.argv[1:] if a.startswith("--")}
nombres = args or list(PIEZAS)
CONJ = os.path.join(RAIZ, "cad", "sc", "CONJUNTO_ojo.sc")


def cli(n):
    t = time.time()
    try:
        r = PIEZAS[n]().construir()
        v = sum(c["volume_mm3"] for c in r["cuerpos"])
        import mallar                                   # el STL de SolidCraft 0.30 puede traer grietas: se remalla el STEP
        est = mallar.procesar(n)[4]
        return f"[CLI] {n}: OK {len(r['cuerpos'])} cuerpo(s), {v:,.0f} mm³, STL {'estanco' if est else 'CON GRIETAS'}, {time.time()-t:.0f}s"
    except Exception as e:
        return f"[CLI] {n}: ERROR {str(e)[-400:]}"


def vivo(nombres):
    from vivo import Vivo
    v = Vivo()
    try:
        if "--nuevo" in flags:
            v.tool("new_design", {})
        for n in nombres:
            p = PIEZAS[n]()
            p.renombrar_final()
            t = time.time()
            try:
                v.tool("execute", {"command": "component.activate", "params": {"component": "root"}, "verbose": False})
                comps = v.tool("execute", {"command": "component.list", "params": {"compact": True}, "verbose": False})
                if f'"{n}"' in comps:
                    print(f"[APP] {n}: ya existe en el conjunto, se omite (bórralo en la app para rehacerlo)")
                    continue
                v.tool("execute", {"command": "component.create", "params": {"name": n, "activate": True}, "verbose": False})
                v.tool("batch", {"commands": p.script(), "verbose": False})
                print(f"[APP] {n}: construida en la ventana ({time.time()-t:.0f}s)")
            except Exception as e:
                print(f"[APP] {n}: ERROR {str(e)[-300:]}")
            v.tool("execute", {"command": "component.activate", "params": {"component": "root"}, "verbose": False})
            v.tool("execute", {"command": "file.save_as", "params": {"path": CONJ}, "verbose": False})
    finally:
        v.cerrar()


if __name__ == "__main__":
    with ThreadPoolExecutor(6) as ex:
        futs = [] if "--sin-cli" in flags else [ex.submit(cli, n) for n in nombres]
        if "--sin-vivo" not in flags:
            vivo(nombres)
        for f in futs:
            print(f.result())
