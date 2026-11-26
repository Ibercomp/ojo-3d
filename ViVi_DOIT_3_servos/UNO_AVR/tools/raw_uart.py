#!/usr/bin/env python3
"""Ojo UART v1 codec and monitor. Opens/reset Uno; never arms its outputs."""
import argparse
import binascii
import json
import secrets
import struct
import time
from pathlib import Path
import serial


def encode(kind, session, seq, stamp, payload=b''):
    if len(payload)>48:
        raise ValueError('payload >48')
    body=struct.pack('<BBBIHI',1,kind,len(payload),session,seq,stamp)+payload
    body+=struct.pack('<H',binascii.crc_hqx(body,0xffff))
    out=bytearray([0]);pos=0;code=1
    for b in body:
        if b:
            out.append(b);code+=1
        else:
            out[pos]=code;pos=len(out);out.append(0);code=1
    out[pos]=code;out.append(0)
    return bytes(out)


def decode(encoded):
    if not 0<len(encoded)<=64:
        raise ValueError('invalid length')
    raw=bytearray();i=0
    while i<len(encoded):
        code=encoded[i];i+=1
        if not code or i+code-1>len(encoded):
            raise ValueError('bad COBS')
        raw.extend(encoded[i:i+code-1]);i+=code-1
        if code!=255 and i<len(encoded):
            raw.append(0)
    if len(raw)<15 or raw[0]!=1 or raw[2]>48 or len(raw)!=15+raw[2]:
        raise ValueError('bad header')
    if struct.unpack_from('<H',raw,len(raw)-2)[0]!=binascii.crc_hqx(raw[:-2],0xffff):
        raise ValueError('bad CRC')
    _,kind,_,session,seq,stamp=struct.unpack_from('<BBBIHI',raw)
    return dict(kind=kind,session=session,seq=seq,time_ms=stamp,payload=bytes(raw[13:-2]))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True)
    p.add_argument('--seconds',type=float,default=5)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    s=serial.Serial(port=None,baudrate=250000,timeout=.01,write_timeout=.1,exclusive=True)
    s.dtr=s.rts=True;s.port=args.port
    session=secrets.randbits(32) or 1
    buf=bytearray();bad=0;telemetry=0;config=None;first=None;last=None;off_ack=False
    with s,args.output.open('x') as out:
        time.sleep(2.3);s.reset_input_buffer();start=time.monotonic()
        s.write(b'\0'+encode(1,session,1,0))
        try:
            while time.monotonic()-start<args.seconds:
                for b in s.read(max(1,min(s.in_waiting,256))):
                    if b:
                        buf.append(b)
                        if len(buf)>64:
                            buf=bytearray([255]*65)
                        continue
                    if not buf:
                        continue
                    try:
                        frame=decode(buf)
                    except ValueError:
                        bad+=1;buf.clear();continue
                    buf.clear()
                    if frame['session']!=session:
                        continue
                    payload=frame.pop('payload');frame['payload_hex']=payload.hex();frame['host_elapsed']=time.monotonic()-start
                    if frame['kind']==0x81:
                        config=payload
                        assert len(config)==48 and config[0]==3 and config[2]==1
                        assert list(struct.unpack_from('<3H',config,8))==[1560,1470,1810]
                    elif frame['kind']==0x82:
                        assert len(payload)==24 and not payload[14]&1,'Outputs unexpectedly active'
                        frame['angles_cdeg']=struct.unpack_from('<3h',payload)
                        frame['rx_errors'],frame['bad_frames'],frame['missed_ticks']=struct.unpack_from('<3H',payload,16)
                        telemetry+=1;first=frame if first is None else first;last=frame
                    out.write(json.dumps(frame)+'\n');out.flush()
            assert config is not None and telemetry>0,'Missing CONFIG/telemetry'
        finally:
            if config is not None:
                s.write(encode(2,session,2,0,b'\0')) # OFF accepted irrespective of timestamp.
                deadline=time.monotonic()+.25
                while time.monotonic()<deadline and not off_ack:
                    for b in s.read(max(1,min(s.in_waiting,256))):
                        if b:
                            buf.append(b)
                            continue
                        if not buf:
                            continue
                        try:
                            packet=decode(buf)
                            off_ack=(packet['kind']==0x83 and packet['session']==session
                                     and packet['seq']==2 and packet['payload']==b'\0\x02')
                        except ValueError:
                            pass
                        buf.clear()
                        if off_ack:
                            break
                assert off_ack,'No OFF acknowledgement'
    print(json.dumps(dict(telemetry=telemetry,bad_wire=bad,off_ack=off_ack,first=first,last=last)))


if __name__=='__main__':
    main()
