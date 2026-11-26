"""Capa mínima para generar scripts de comandos SolidCraft (JSON) desde Python.

Cada pieza es una lista de comandos que construye UN cuerpo final en coordenadas de
montaje (origen O = centro de las esferas). Los cuerpos auxiliares se crean con
operation "new" y se combinan explícitamente con solid.combine, para que ninguna
operación "auto" decida por nosotros.

Planos de sketch:
  XY: x→X, y→Y  (normal +Z)      XZ: x→X, y→-Z (normal +Y)      YZ: x→Y, y→Z (normal +X)
"""
import json, math, os, subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.expanduser("~/.local/bin/solidcraft-cli")


def f(v):
    return float(round(v, 4))


class Pieza:
    def __init__(self, nombre):
        self.nombre = nombre
        self.cmds = []
        self.n = 0
        self.cuerpo = None  # nombre del cuerpo principal

    # ---------- utilidades internas ----------
    def _tmp(self, base="T"):
        self.n += 1
        return f"{self.nombre[:3]}_{base}{self.n}"

    def c(self, command, **params):
        self.cmds.append({"command": command, "params": params})

    def _poner(self, cuerpo, op):
        """op: 'base' (será el principal), 'join', 'cut', 'intersect' o 'keep' (cuerpo suelto)."""
        if op == "base":
            self.cuerpo = cuerpo
        elif op in ("join", "cut", "intersect"):
            self.c("solid.combine", target=self.cuerpo, tools=[cuerpo], operation=op)
        return cuerpo

    # ---------- primitivas ----------
    def caja(self, xr, yr, zr, op="join", nombre=None):
        b = nombre or self._tmp("Caja")
        self.c("solid.box", length=f(xr[1] - xr[0]), width=f(yr[1] - yr[0]), height=f(zr[1] - zr[0]),
               center=[f((xr[0] + xr[1]) / 2), f((yr[0] + yr[1]) / 2), f((zr[0] + zr[1]) / 2)],
               operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def cilindro(self, base, eje, d, h, op="join", nombre=None):
        """eje: 'X','Y','Z' o vector; base = centro de la cara inicial; h a lo largo de +eje."""
        b = nombre or self._tmp("Cil")
        self.c("solid.cylinder", diameter=f(d), height=f(h), base=[f(v) for v in base], axis=eje,
               operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def cil_x(self, x0, x1, y, z, d, op="join"):
        return self.cilindro([min(x0, x1), y, z], "X", d, abs(x1 - x0), op)

    def cil_y(self, y0, y1, x, z, d, op="join"):
        return self.cilindro([x, min(y0, y1), z], "Y", d, abs(y1 - y0), op)

    def cil_z(self, z0, z1, x, y, d, op="join"):
        return self.cilindro([x, y, min(z0, z1)], "Z", d, abs(z1 - z0), op)

    def esfera(self, r, op="join", centro=(0, 0, 0), nombre=None):
        b = nombre or self._tmp("Esf")
        self.c("solid.sphere", radius=f(r), center=[f(v) for v in centro], operation="new", body_name=b, name=b)
        return self._poner(b, op)

    # ---------- perfiles ----------
    def _sketch(self, plano, offset=0.0):
        s = self._tmp("Sk")
        p = {"plane": plano, "name": s}
        if offset:
            p["offset"] = f"{f(offset)} mm"
        self.c("sketch.create", **p)
        return s

    def poligono(self, plano, pts, x0, x1, op="join", offset_es_normal=True):
        """Polígono cerrado en un plano principal, extruido entre dos cotas de la normal.
        plano 'YZ': pts=(Y,Z), cotas en X.  'XY': pts=(X,Y), cotas en Z.  'XZ': pts=(X,Z), cotas en Y."""
        lo, hi = min(x0, x1), max(x0, x1)
        if plano == "XZ":
            sk_pts = [[f(a), f(-b)] for a, b in pts]
        else:
            sk_pts = [[f(a), f(b)] for a, b in pts]
        s = self._sketch(plano, lo)
        self.c("sketch.line", points=sk_pts + [sk_pts[0]], infer=False)
        self.c("sketch.finish")
        b = self._tmp("Ext")
        self.c("solid.extrude", sketch=s, distance=f"{f(hi - lo)} mm", operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def sector(self, plano_x0, plano_x1, r0, r1, a0, a1, op="join", n_min=0, redondeo=0.0):
        """Sector anular en el plano YZ (alrededor del eje X), extruido de x0 a x1.
        Ángulos α desde +Z hacia +Y (grados). r0 puede ser 0 (sector macizo)."""
        lo, hi = min(plano_x0, plano_x1), max(plano_x0, plano_x1)
        s = self._sketch("YZ", lo)

        def P(r, a):
            a = math.radians(a)
            return [f(r * math.sin(a)), f(r * math.cos(a))]
        # en el sketch YZ, x=Y, y=Z: el ángulo matemático (desde +x antihorario) es 90-α
        if r0 > 0:
            self.c("sketch.line", points=[P(r1, a0), P(r0, a0)], infer=False)          # l1
            self.c("sketch.line", points=[P(r0, a1), P(r1, a1)], infer=False)          # l2
            self.c("sketch.arc.center_point", center=[0, 0], start="l2.end", end="l1.start")
            self.c("sketch.arc.center_point", center=[0, 0], start="l1.end", end="l2.start", clockwise=True)
        else:
            self.c("sketch.line", points=[P(r1, a0), [0, 0], P(r1, a1)], infer=False)  # l1, l2
            self.c("sketch.arc.center_point", center=[0, 0], start="l2.end", end="l1.start")
        if redondeo > 0:   # esquinas redondeadas (sin picos): las exteriores siempre, las interiores si es anular
            esq = ["l1.start", "l2.end"] + (["l1.end", "l2.start"] if r0 > 0 else [])
            self.c("sketch.fillet", points=esq, radius=f(redondeo))
        self.c("sketch.finish")
        b = self._tmp("Sec")
        self.c("solid.extrude", sketch=s, distance=f"{f(hi - lo)} mm", operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def luna(self, Ri, Ro, a0, a1, op="join", nombre=None):
        """Cáscara esférica entre radios Ri..Ro y ángulos α0..α1 alrededor del eje X.
        Se hace con esferas reales ∩ cuña (la revolución deja polos que el núcleo booleano
        de SolidCraft 0.30 no une bien con sólidos planos)."""
        b = self.esfera(Ro, op="keep", nombre=nombre or self._tmp("Luna"))
        i = self.esfera(Ri, op="keep")
        self.c("solid.combine", target=b, tools=[i], operation="cut")
        w = self.sector(-Ro - 2, Ro + 2, 0, Ro + 5, a0, a1, op="keep")
        self.c("solid.combine", target=b, tools=[w], operation="intersect")
        return self._poner(b, op)

    def luna_recortada(self, Ri, Ro, a0, a1, xr, op="join", nombre=None):
        """Cáscara Ri..Ro entre α0..α1 alrededor de X y recortada en |X| <= xr, como UNA revolución de un
        perfil que no toca el eje (sin polos ni booleanas esfera-plano, frágiles en SolidCraft 0.30)."""
        s = self._sketch("XZ")
        yi, yo = math.sqrt(Ri ** 2 - xr ** 2), math.sqrt(Ro ** 2 - xr ** 2)   # sketch y = -Z (perfil en Z>0)
        self.c("sketch.line", points=[[f(xr), f(-yi)], [f(xr), f(-yo)]], infer=False)      # l1: A→B
        self.c("sketch.line", points=[[f(-xr), f(-yo)], [f(-xr), f(-yi)]], infer=False)    # l2: C→D
        self.c("sketch.arc.center_point", center=[0, 0], start="l1.end", end="l2.start", clockwise=True)
        self.c("sketch.arc.center_point", center=[0, 0], start="l2.end", end="l1.start")
        self.c("sketch.finish")
        b = nombre or self._tmp("LunaR")
        self.c("solid.revolve", sketch=s, axis="X", angle=f"{f(a1 - a0)} deg", operation="new", body_name=b, name=b)
        if abs(a0) > 1e-9:
            self.c("solid.move", bodies=[b], axis=[1, 0, 0], angle=f"{f(-a0)} deg")
        return self._poner(b, op)

    def luna_radial(self, Ri, Ro, a0, a1, th, op="join", nombre=None):
        """Cáscara Ri..Ro entre α0..α1 alrededor de X que termina en CORTES RADIALES (conos por O de semiángulo
        th respecto a ±X): el canto conserva todo el espesor (sin filo) y casa con el escalón radial del casquete."""
        s = self._sketch("XZ")
        c, sn = math.cos(math.radians(th)), math.sin(math.radians(th))
        self.c("sketch.line", points=[[f(Ri * c), f(-Ri * sn)], [f(Ro * c), f(-Ro * sn)]], infer=False)     # l1
        self.c("sketch.line", points=[[f(-Ro * c), f(-Ro * sn)], [f(-Ri * c), f(-Ri * sn)]], infer=False)   # l2
        self.c("sketch.arc.center_point", center=[0, 0], start="l1.end", end="l2.start", clockwise=True)
        self.c("sketch.arc.center_point", center=[0, 0], start="l2.end", end="l1.start")
        self.c("sketch.finish")
        b = nombre or self._tmp("LunaRad")
        self.c("solid.revolve", sketch=s, axis="X", angle=f"{f(a1 - a0)} deg", operation="new", body_name=b, name=b)
        if abs(a0) > 1e-9:
            self.c("solid.move", bodies=[b], axis=[1, 0, 0], angle=f"{f(-a0)} deg")
        return self._poner(b, op)

    def lagrima(self, plano, u, v, d, x0, x1, arriba, op="join", truncada=1.1):
        """Agujero en lágrima (techo a 45°, autosoportado) en un plano principal, extruido entre x0..x1 de la normal.
        (u, v) centro en coordenadas del plano como en `poligono`. arriba: +1/-1 = sentido de v que queda hacia arriba
        al imprimir, o un vector (du, dv) en coordenadas del plano. Vértice truncado a truncada·r."""
        r = d / 2; k = math.sqrt(0.5); h = truncada * r
        du, dv = (0.0, float(arriba)) if isinstance(arriba, (int, float)) else arriba
        n = math.hypot(du, dv); du, dv = du / n, dv / n
        pu, pv = -dv, du                                   # perpendicular
        C = lambda a, b: (u + a * du + b * pu, v + a * dv + b * pv)    # a: hacia el vértice, b: de lado
        dx = r * k - (h - r * k)
        t1, q1, q2, t2 = C(r * k, r * k), C(h, dx), C(h, -dx), C(r * k, -r * k)
        conv = (lambda a, b: [f(a), f(-b)]) if plano == "XZ" else (lambda a, b: [f(a), f(b)])
        lo, hi = min(x0, x1), max(x0, x1)
        s = self._sketch(plano, lo)
        S = [conv(*q) for q in (t1, q1, q2, t2)]
        self.c("sketch.line", points=S, infer=False)                                     # l1 l2 l3
        Cc = conv(u, v); Bp = conv(*C(-r, 0))
        ang = lambda q: math.atan2(q[1] - Cc[1], q[0] - Cc[0])
        a_s, a_e, a_b = ang(S[3]), ang(S[0]), ang(Bp)
        ccw_pasa = (a_b - a_s) % (2 * math.pi) < (a_e - a_s) % (2 * math.pi)
        self.c("sketch.arc.center_point", center=Cc, start="l3.end", end="l1.start", clockwise=not ccw_pasa)
        self.c("sketch.finish")
        b = self._tmp("Lagrima")
        self.c("solid.extrude", sketch=s, distance=f"{f(hi - lo)} mm", operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def oreja_revolucion(self, tramos, Ra, a0, a1, lado, op="join"):
        """Oreja de párpado como UNA revolución alrededor de X de un perfil escalonado (x, ρ):
        tramos = [(x_ini, x_fin, ρ_interior)], ρ exterior = Ra, entre α0..α1. lado = +1/-1 (espejo en X)."""
        pts = []
        for a, b, r0 in tramos:
            pts += [(a, r0), (b, r0)]
        pts += [(tramos[-1][1], Ra), (tramos[0][0], Ra)]
        lim = []
        for x, r in pts:                      # quita duplicados consecutivos
            if not lim or (abs(lim[-1][0] - x) > 1e-9 or abs(lim[-1][1] - r) > 1e-9):
                lim.append((x, r))
        s = self._sketch("XZ")
        sk = [[f(lado * x), f(-r)] for x, r in lim]     # sketch y = -Z: el perfil vive en Z>0 (α=0)
        self.c("sketch.line", points=sk + [sk[0]], infer=False)
        self.c("sketch.finish")
        b = self._tmp("Oreja")
        self.c("solid.revolve", sketch=s, axis="X", angle=f"{f(a1 - a0)} deg", operation="new", body_name=b, name=b)
        if abs(a0) > 1e-9:
            self.c("solid.move", bodies=[b], axis=[1, 0, 0], angle=f"{f(-a0)} deg")
        return self._poner(b, op)

    def rombo(self, eje, c1, c2, d, a, b, op="join"):
        """agujero en rombo (autosoportado a 45°) a lo largo de `eje` ('Y' o 'X'), centro (c1, c2) en el plano
        perpendicular, ancho entre vértices d, entre las cotas a..b del eje. Vértices apuntando a ±Z de impresión."""
        r = d / 2
        if eje == "Y":       # plano XZ: pts (X, Z)
            pts = [(c1, c2 + r), (c1 + r, c2), (c1, c2 - r), (c1 - r, c2)]
            return self.poligono("XZ", pts, a, b, op=op)
        pts = [(c1 + r, c2), (c1, c2 + r), (c1 - r, c2), (c1, c2 - r)]   # eje X: plano YZ, pts (Y, Z)
        return self.poligono("YZ", pts, a, b, op=op)

    def luna_con_espigas(self, Ri, Ro, a0, a1, xt, e, op="join", nombre=None):
        """Cáscara Ri..Ro entre α0..α1 alrededor de X, recortada en |X| <= xt y terminada en dos ESPIGAS
        (anillo prismático de largo e, misma sección que el corte) que entran en la ranura del acople.
        Una sola revolución: sin booleanas."""
        s = self._sketch("XZ")
        yi, yo = math.sqrt(Ri ** 2 - xt ** 2), math.sqrt(Ro ** 2 - xt ** 2)    # sketch y = -ρ
        self.c("sketch.line", points=[[f(xt), f(-yi)], [f(xt + e), f(-yi)], [f(xt + e), f(-yo)], [f(xt), f(-yo)]],
               infer=False)                                                          # l1 l2 l3
        self.c("sketch.line", points=[[f(-xt), f(-yo)], [f(-xt - e), f(-yo)], [f(-xt - e), f(-yi)], [f(-xt), f(-yi)]],
               infer=False)                                                          # l4 l5 l6
        self.c("sketch.arc.center_point", center=[0, 0], start="l3.end", end="l4.start", clockwise=True)
        self.c("sketch.arc.center_point", center=[0, 0], start="l6.end", end="l1.start")
        self.c("sketch.finish")
        b = nombre or self._tmp("LunaE")
        self.c("solid.revolve", sketch=s, axis="X", angle=f"{f(a1 - a0)} deg", operation="new", body_name=b, name=b)
        if abs(a0) > 1e-9:
            self.c("solid.move", bodies=[b], axis=[1, 0, 0], angle=f"{f(-a0)} deg")
        return self._poner(b, op)

    def envolvente_circulos(self, plano, circulos, x0, x1, op="join"):
        """Extrusión del contorno convexo (arcos + tangentes) de círculos [(u, v, r)] dados en orden ANTIHORARIO
        en el plano del sketch (YZ: u=Y, v=Z). Cada círculo debe pertenecer al contorno."""
        n = len(circulos)
        if n > 2:   # orden antihorario alrededor del centroide
            cu = sum(c[0] for c in circulos) / n; cv = sum(c[1] for c in circulos) / n
            circulos = sorted(circulos, key=lambda c: math.atan2(c[1] - cv, c[0] - cu))
        T = []   # (punto de salida en i, punto de llegada en i+1)
        for i in range(n):
            (u1, v1, r1), (u2, v2, r2) = circulos[i], circulos[(i + 1) % n]
            du, dv = u2 - u1, v2 - v1; L = math.hypot(du, dv); du, dv = du / L, dv / L
            k = (r1 - r2) / L; h = math.sqrt(1 - k * k)
            nu, nv = k * du + h * dv, k * dv - h * du          # normal exterior (a la derecha del avance)
            T.append(((u1 + r1 * nu, v1 + r1 * nv), (u2 + r2 * nu, v2 + r2 * nv)))
        s = self._sketch(plano, min(x0, x1))
        for i in range(n):
            a, b = T[i]
            self.c("sketch.line", points=[[f(a[0]), f(a[1])], [f(b[0]), f(b[1])]], infer=False)
        for i in range(n):              # arco en el círculo i+1: de la llegada de T[i] a la salida de T[i+1]
            j = (i + 1) % n
            u, v, _ = circulos[j]
            self.c("sketch.arc.center_point", center=[f(u), f(v)], start=f"l{i + 1}.end", end=f"l{j + 1}.start")
        self.c("sketch.finish")
        b = self._tmp("Env")
        self.c("solid.extrude", sketch=s, distance=f"{f(abs(x1 - x0))} mm", operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def contorno(self, plano, tramos, x0, x1, op="join"):
        """Perfil cerrado de rectas y arcos EXACTOS extruido entre x0..x1 de la normal. tramos (en orden antihorario
        en coordenadas del plano; 'XZ' en (X, Z) de montaje): ('L', p0, p1) | ('A', centro, p0, p1, horario).
        Cada extremo de arco debe coincidir con un extremo de recta: se ancla a él por referencia (lN.start/end),
        así el perfil cierra aunque el redondeo numérico separe micras los puntos."""
        sg = -1 if plano == "XZ" else 1
        P = lambda q: [f(q[0]), f(sg * q[1])]
        s = self._sketch(plano, min(x0, x1))
        ref, k = {}, 0
        for t in tramos:
            if t[0] == "L":
                k += 1
                self.c("sketch.line", points=[P(t[1]), P(t[2])], infer=False)
                ref.setdefault(tuple(P(t[1])), f"l{k}.start"); ref.setdefault(tuple(P(t[2])), f"l{k}.end")
        for t in tramos:
            if t[0] == "A":
                self.c("sketch.arc.center_point", center=P(t[1]), start=ref[tuple(P(t[2]))], end=ref[tuple(P(t[3]))],
                       clockwise=bool(t[4]) != (sg < 0))
        self.c("sketch.finish")
        b = self._tmp("Cont")
        self.c("solid.extrude", sketch=s, distance=f"{f(abs(x1 - x0))} mm", operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def seccion_redondeada(self, origen, x_dir, y_dir, alto, ancho, r):
        """boceto en un plano cualquiera (origen, x_dir = altura, y_dir = lateral): rectángulo de alto × ancho apoyado
        en u = 0 y centrado en v, con las dos esquinas de ARRIBA redondeadas r (sección de pata para solevar)"""
        s = self._tmp("Sec")
        self.c("sketch.create", plane={"origin": [f(v) for v in origen], "x_dir": [f(v) for v in x_dir],
                                       "y_dir": [f(v) for v in y_dir]}, name=s)
        a, w = alto, ancho / 2
        self.c("sketch.line", points=[[0, f(-w)], [0, f(w)]], infer=False)                   # l1 base
        self.c("sketch.line", points=[[0, f(w)], [f(a - r), f(w)]], infer=False)              # l2 lado
        self.c("sketch.line", points=[[f(a), f(w - r)], [f(a), f(-w + r)]], infer=False)      # l3 arriba
        self.c("sketch.line", points=[[f(a - r), f(-w)], [0, f(-w)]], infer=False)            # l4 lado
        self.c("sketch.arc.center_point", center=[f(a - r), f(w - r)], start="l2.end", end="l3.start", clockwise=True)
        self.c("sketch.arc.center_point", center=[f(a - r), f(-w + r)], start="l3.end", end="l4.start", clockwise=True)
        self.c("sketch.finish")
        return s

    def rect_redondeado(self, plano, u0, u1, v0, v1, r, x0, x1, op="join", recto=None):
        """rectángulo de esquinas redondeadas (arcos verdaderos) extruido entre x0..x1 a lo largo de la normal.
        recto='u0' / 'u1': las dos esquinas de ese lado quedan en ángulo recto (p. ej. donde arranca una pala)."""
        s = self._sketch(plano, min(x0, x1))
        sg = -1 if plano == "XZ" else 1
        P = lambda u, v: [f(u), f(sg * v)]
        cw = (sg < 0)
        if recto in ("u0", "u1"):
            ur, uc = (u0, u1) if recto == "u0" else (u1, u0)      # lado recto / lado redondeado
            d = -r if uc > ur else r                               # hacia dentro desde el lado redondeado
            self.c("sketch.line", points=[P(ur, v0), P(uc + d, v0)], infer=False)               # l1
            self.c("sketch.line", points=[P(uc, v0 + r), P(uc, v1 - r)], infer=False)           # l2
            self.c("sketch.line", points=[P(uc + d, v1), P(ur, v1), P(ur, v0)], infer=False)    # l3 l4
            ccw = (uc > ur) != cw
            self.c("sketch.arc.center_point", center=P(uc + d, v0 + r), start="l1.end", end="l2.start", clockwise=not ccw)
            self.c("sketch.arc.center_point", center=P(uc + d, v1 - r), start="l2.end", end="l3.start", clockwise=not ccw)
            self.c("sketch.finish")
            b = self._tmp("RRed")
            self.c("solid.extrude", sketch=s, distance=f"{f(abs(x1 - x0))} mm", operation="new", body_name=b, name=b)
            return self._poner(b, op)
        self.c("sketch.line", points=[P(u0 + r, v0), P(u1 - r, v0)], infer=False)   # l1 abajo
        self.c("sketch.line", points=[P(u1, v0 + r), P(u1, v1 - r)], infer=False)   # l2 derecha
        self.c("sketch.line", points=[P(u1 - r, v1), P(u0 + r, v1)], infer=False)   # l3 arriba
        self.c("sketch.line", points=[P(u0, v1 - r), P(u0, v0 + r)], infer=False)   # l4 izquierda
        cw = (sg < 0)
        for (cu, cv), a, b in (((u1 - r, v0 + r), "l1.end", "l2.start"), ((u1 - r, v1 - r), "l2.end", "l3.start"),
                               ((u0 + r, v1 - r), "l3.end", "l4.start"), ((u0 + r, v0 + r), "l4.end", "l1.start")):
            self.c("sketch.arc.center_point", center=P(cu, cv), start=a, end=b, clockwise=cw)
        self.c("sketch.finish")
        b = self._tmp("RRed")
        self.c("solid.extrude", sketch=s, distance=f"{f(abs(x1 - x0))} mm", operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def casquete_polar(self, arcos, lineas, a0, a1, lado, op="join"):
        """Revolución alrededor de X de un perfil (x, ρ) hecho de ARCOS centrados en O y líneas.
        arcos: [((x0, ρ0), (x1, ρ1))] con x creciente (para lado=+1); lineas: listas de puntos donde cada
        punto es (x, ρ) o una referencia 'a1.start', 'a2.end'... El perfil vive en el semiplano α=0."""
        s = self._sketch("XZ")
        P = lambda q: q if isinstance(q, str) else [f(lado * q[0]), f(-q[1])]
        for (p0, p1) in arcos:   # con x creciente el ángulo crece (antihorario); el espejo lo invierte
            self.c("sketch.arc.center_point", center=[0, 0], start=P(p0), end=P(p1), clockwise=(lado < 0))
        for pts in lineas:
            self.c("sketch.line", points=[P(q) for q in pts], infer=False)
        self.c("sketch.finish")
        b = self._tmp("Casquete")
        self.c("solid.revolve", sketch=s, axis="X", angle=f"{f(a1 - a0)} deg", operation="new", body_name=b, name=b)
        if abs(a0) > 1e-9:
            self.c("solid.move", bodies=[b], axis=[1, 0, 0], angle=f"{f(-a0)} deg")
        return self._poner(b, op)

    def unir_herramientas(self, cuerpos):
        """une varios cuerpos auxiliares en el primero (devuelve su nombre)"""
        for q in cuerpos[1:]:
            self.c("solid.combine", target=cuerpos[0], tools=[q], operation="join")
        return cuerpos[0]

    def casquete_z(self, Ri, Ro, z_corte, op="join", nombre=None):
        """Cáscara esférica alrededor de +Z, desde el polo delantero hasta el plano z=z_corte."""
        s = self._sketch("XZ")
        xo = math.sqrt(Ro ** 2 - z_corte ** 2)
        xi = math.sqrt(Ri ** 2 - z_corte ** 2)
        # sketch y = -Z
        self.c("sketch.line", points=[[f(xo), f(-z_corte)], [f(xi), f(-z_corte)]], infer=False)  # l1
        self.c("sketch.line", points=[[0, f(-Ri)], [0, f(-Ro)]], infer=False)                    # l2
        self.c("sketch.arc.center_point", center=[0, 0], start="l2.end", end="l1.start")
        self.c("sketch.arc.center_point", center=[0, 0], start="l1.end", end="l2.start", clockwise=True)
        self.c("sketch.finish")
        b = nombre or self._tmp("Casq")
        self.c("solid.revolve", sketch=s, axis="Z", angle="360 deg", operation="new", body_name=b, name=b)
        return self._poner(b, op)

    def renombrar_final(self):
        if self.cuerpo != self.nombre:
            self.c("body.rename", body=self.cuerpo, name=self.nombre)
            self.cuerpo = self.nombre

    # ---------- ejecución ----------
    def script(self):
        return list(self.cmds)

    def construir(self, salida_step=True, salida_stl=True):
        self.renombrar_final()
        d = os.path.join(RAIZ, "cad")
        sp = os.path.join(d, "scripts", f"{self.nombre}.json")
        with open(sp, "w") as fh:
            json.dump(self.cmds, fh, indent=1, ensure_ascii=False)
        args = [CLI, "run", sp, "--save", os.path.join(d, "sc", f"{self.nombre}.sc")]
        if salida_step:
            args += ["--out", os.path.join(d, "step", f"{self.nombre}.step")]
        if salida_stl:
            args += ["--out", os.path.join(d, "stl", f"{self.nombre}.stl")]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{self.nombre}: solidcraft-cli run falló\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
        # medida desde el STEP con OpenCascade (segundos); `eval` recalculaba todo el historial
        import mallar
        sh = mallar.leer_step(os.path.join(d, "step", f"{self.nombre}.step"))
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
        from OCP.BRepCheck import BRepCheck_Analyzer
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g)
        cuerpos = [{"name": self.nombre, "volume_mm3": g.Mass(), "valido": BRepCheck_Analyzer(sh).IsValid()}]
        errores = []
        return {"pieza": self.nombre, "cuerpos": cuerpos, "errores": errores}
