// OJ19 motion datagrams: fixed little-endian fields, no packed-struct ABI.
#pragma once
#include "control_protocol.h"
typedef struct { uint32_t token,seq,last_ms; int received; } ojo_udp_session;
static uint16_t udp_u16(const uint8_t*p){return p[0]|((uint16_t)p[1]<<8);}
static uint32_t udp_u32(const uint8_t*p){return udp_u16(p)|((uint32_t)udp_u16(p+2)<<16);}
static void udp_put16(uint8_t*p,uint16_t v){p[0]=v;p[1]=v>>8;}
static void udp_put32(uint8_t*p,uint32_t v){udp_put16(p,v);udp_put16(p+2,v>>16);}
// A session never powers on motors. Old, reordered, stale or malformed packets
// cannot keep the watchdog alive. Arithmetic also works across uptime wrap.
static int udp_decode(ojo_udp_session*s,const uint8_t*p,size_t n,uint32_t now, ojo_command*c){
 if(!s->token)return 0;
 if((uint32_t)(now-s->last_ms)>700){s->token=0;return 0;}
 if(n!=24||memcmp(p,"OJ19",4)||udp_u32(p+4)!=s->token||p[23]||p[22]>1)return 0;
 uint32_t seq=udp_u32(p+8);int32_t age=(int32_t)(now-udp_u32(p+12));
 if((s->received&&(int32_t)(seq-s->seq)<=0)||age>200||age< -100)return 0;
 int yaw=(int16_t)udp_u16(p+16),pitch=(int16_t)udp_u16(p+18),lid=udp_u16(p+20);
 if(abs(yaw)>5500||abs(pitch)>3500||lid>(p[22]?6000:3200))return 0;
 memset(c,0,sizeof(*c));c->kind=OJO_FOLLOW;c->angle[0]=yaw*.01f;c->angle[1]=pitch*.01f;c->angle[2]=lid*.01f;c->rest=p[22];
 c->has[0]=c->has[1]=c->has[2]=1;s->seq=seq;s->received=1;s->last_ms=now;return 1;
}
