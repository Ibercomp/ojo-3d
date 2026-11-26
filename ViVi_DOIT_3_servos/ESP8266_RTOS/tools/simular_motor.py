#!/usr/bin/env python3
"""Local HTTP simulator for the native C motion engine; no servo/network hardware.
Use with ZTrak's verificar_comportamiento --simulador=127.0.0.1:8123.
"""
import argparse, ctypes, http.server, json, pathlib, subprocess, tempfile, threading, time, socket, struct, secrets
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8123);p.add_argument('--log',required=True);p.add_argument('--faults',action='store_true',help='inject 350 ms timeouts at seconds 2 and 11');p.add_argument('--udp',action='store_true',help='raw binary UDP on HTTP port + 1');p.add_argument('--drop-commands',action='store_true',help='with --faults also drop motion packets during the 350 ms outages');a=p.parse_args()
base=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='ojo-host-') as tmp:
 libpath=str(pathlib.Path(tmp)/'motor.so')
 subprocess.run(['cc','-std=c99','-shared','-fPIC','-O1',str(base/'tests/host_motor.c'),'-lm','-o',libpath],check=True)
 lib=ctypes.CDLL(libpath);lib.host_tick.argtypes=[ctypes.c_float];lib.host_request.argtypes=[ctypes.c_char_p];lib.host_state.restype=ctypes.c_char_p;lib.host_init()
 lib.host_udp.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_uint32];lib.host_udp_open.argtypes=[ctypes.c_uint32,ctypes.c_uint32];lib.host_udp_token.restype=ctypes.c_uint32
 lock=threading.Lock();start=time.monotonic();faults=[2.,11.] if a.faults else [];control_start=[]
 with open(a.log,'x') as log:
  def record(kind,**kw):
   data=json.loads(lib.host_state());data.update(t=time.monotonic()-start,kind=kind,**kw);log.write(json.dumps(data)+'\n');log.flush()
  def ticks():
   next_tick=time.monotonic()
   while True:
    next_tick+=.02
    time.sleep(max(0,next_tick-time.monotonic()))
    with lock:lib.host_tick(.02);record('tick')
  def state():
   s=json.loads(lib.host_state())
   if a.udp:s.update(udp_port=a.port+1,udp_session=lib.host_udp_token(),diag=dict(uptime_ms=int((time.monotonic()-start)*1000),wifi_drops=0,i2c_errors=0,drive_gap_ms=20))
   return s
  def udp_loop():
   sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',a.port+1))
   while True:
    packet,peer=sock.recvfrom(64)
    with lock:
     elapsed=time.monotonic()-control_start[0] if control_start else 0
     if a.faults and a.drop_commands and any(t<=elapsed<t+.35 for t in (2.,11.)):
      record('dropped_command');continue
     now=int((time.monotonic()-start)*1000)
     if lib.host_udp(packet,len(packet),now)!=200:continue
     s=state();flags=1|2|(4 if s['parpadeando'] else 0)|(8 if s['reposo'] else 0)|16
     reply=struct.pack('<4sIIIhhhHB3xHHH2x',b'OS19',s['udp_session'],struct.unpack_from('<I',packet,8)[0],now,*[round(x*100) for x in s['actual']],round(s['parpado_seguimiento']*100),flags,0,0,20)
     record('udp',seq=struct.unpack_from('<I',packet,8)[0])
    elapsed=time.monotonic()-control_start[0] if control_start else 0
    dropping=a.faults and any(t<=elapsed<t+.35 for t in (2.,11.))
    if not dropping:sock.sendto(reply,peer)
  class Handler(http.server.BaseHTTPRequestHandler):
   protocol_version='HTTP/1.1'
   def log_message(self,*args):pass
   def do_GET(self):
    with lock:
     if a.udp and self.path=='/udp':
      lib.host_udp_open(secrets.randbits(32)|1,int((time.monotonic()-start)*1000));status=200
     else:status=lib.host_request(self.path.encode())
     body=json.dumps(state()).encode();record('request',uri=self.path,status=status)
     if self.path=="/encender" and not control_start:control_start.append(time.monotonic())
     delay=bool(faults and control_start and time.monotonic()-control_start[0]>=faults[0])
     if delay:
      faults.pop(0);record("delay",uri=self.path,delay_ms=350)
    if delay:time.sleep(.35)
    try:
     self.send_response(status);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    except (BrokenPipeError,ConnectionResetError):pass
  server=http.server.ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
  threading.Thread(target=ticks,daemon=True).start()
  if a.udp:threading.Thread(target=udp_loop,daemon=True).start()
  print('Simulador local en 127.0.0.1:'+str(a.port),flush=True)
  server.serve_forever()
