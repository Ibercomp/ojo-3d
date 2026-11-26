"""Puente en vivo con la app de SolidCraft abierta (canal de control 127.0.0.1:7878).

Habla JSON-RPC (MCP) con `solidcraft-cli mcp --connect`, como cualquier cliente MCP,
para ver en su ventana lo que se construye.

  .venv/bin/python herramientas/vivo.py abrir cad/sc/P01_globo.sc
  .venv/bin/python herramientas/vivo.py script cad/scripts/P03_parpado_sup.json
  .venv/bin/python herramientas/vivo.py tool inspect_design '{"measure":false,"sketches":false}'
"""
import json, os, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.expanduser("~/.local/bin/solidcraft-cli")
PUERTO = os.environ.get("SOLIDCRAFT_CONTROL_PORT", "7878")


class Vivo:
    def __init__(self):
        self.p = subprocess.Popen([CLI, "mcp", "--connect", f"127.0.0.1:{PUERTO}", "--allow-path", RAIZ],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        self.i = 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "ojo-3d", "version": "1"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

    def _rpc(self, method, params):
        self.i += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.i, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("el servidor MCP se cerró")
            msg = json.loads(line)
            if msg.get("id") == self.i:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def tool(self, name, args):
        r = self._rpc("tools/call", {"name": name, "arguments": args})
        txt = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        if r.get("isError"):
            raise RuntimeError(txt[:2000])
        return txt

    def cerrar(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


if __name__ == "__main__":
    v = Vivo()
    try:
        cmd = sys.argv[1]
        if cmd == "abrir":
            print(v.tool("open", {"path": os.path.abspath(sys.argv[2])})[:800])
        elif cmd == "script":
            cmds = json.load(open(sys.argv[2]))
            print(v.tool("batch", {"commands": cmds, "verbose": False})[:1500])
        elif cmd == "tool":
            print(v.tool(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})[:4000])
    finally:
        v.cerrar()
