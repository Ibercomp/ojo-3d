// Ojo UART v1: COBS + 00, integers LE, CRC16/CCITT-FALSE. No packed ABI.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define RAW_PAYLOAD 48
#define RAW_DECODED 63
#define RAW_WIRE 65
#define RAW_HELLO 0x01
#define RAW_ARM 0x02
#define RAW_STATE 0x03
#define RAW_CENTER 0x04
#define RAW_BLINK 0x05
#define RAW_LIMITS 0x06
#define RAW_TARGET 0x10
#define RAW_CONFIG 0x81
#define RAW_TELEMETRY 0x82
#define RAW_ACK 0x83
// Status: 0 OK, 1 malformed/range, 2 inactive, 3 expired, 4 busy, 5 sequence, 6 unsupported.
typedef struct {uint32_t session,time_ms;uint16_t seq;uint8_t type,length,data[RAW_PAYLOAD];} raw_packet;
typedef struct {uint8_t encoded[RAW_WIRE-1],used,overflow;} raw_decoder;
static uint16_t raw_u16(const uint8_t*p){return p[0]|((uint16_t)p[1]<<8);}
static uint32_t raw_u32(const uint8_t*p){return raw_u16(p)|((uint32_t)raw_u16(p+2)<<16);}
static void raw_put16(uint8_t*p,uint16_t v){p[0]=v;p[1]=v>>8;}
static void raw_put32(uint8_t*p,uint32_t v){raw_put16(p,v);raw_put16(p+2,v>>16);}
static uint16_t raw_crc(const uint8_t*p,size_t n){uint16_t c=0xffff;while(n--){c^=(uint16_t)*p++<<8;for(int i=0;i<8;i++)c=c&0x8000?(uint16_t)((c<<1)^0x1021):(uint16_t)(c<<1);}return c;}
static size_t raw_encode(const raw_packet*p,uint8_t*out){
 if(p->length>RAW_PAYLOAD)return 0;
 uint8_t b[RAW_DECODED];size_t n=15+p->length;b[0]=1;b[1]=p->type;b[2]=p->length;
 raw_put32(b+3,p->session);raw_put16(b+7,p->seq);raw_put32(b+9,p->time_ms);memcpy(b+13,p->data,p->length);raw_put16(b+n-2,raw_crc(b,n-2));
 size_t used=1,pos=0;uint8_t code=1;
 for(size_t i=0;i<n;i++){if(b[i]){out[used++]=b[i];code++;}else{out[pos]=code;pos=used++;code=1;}}
 out[pos]=code;out[used++]=0;return used;
}
// 1 complete valid packet; -1 malformed; 0 waiting/empty delimiter.
static int raw_feed(raw_decoder*s,uint8_t byte,raw_packet*out){
 if(byte){if(s->used<sizeof(s->encoded)&&!s->overflow)s->encoded[s->used++]=byte;else s->overflow=1;return 0;}
 if(!s->used&&!s->overflow)return 0;
 uint8_t b[RAW_DECODED];size_t n=0,i=0,count=s->used;int bad=s->overflow;s->used=s->overflow=0;
 if(bad)return -1;
 while(i<count){uint8_t code=s->encoded[i++];if(!code||i+code-1>count)return -1;
  for(uint8_t k=1;k<code;k++){if(n==sizeof(b))return -1;b[n++]=s->encoded[i++];}
  if(code!=255&&i<count){if(n==sizeof(b))return -1;b[n++]=0;}
 }
 if(n<15||b[0]!=1||b[2]>RAW_PAYLOAD||n!=(size_t)15+b[2]||raw_u16(b+n-2)!=raw_crc(b,n-2))return -1;
 out->type=b[1];out->length=b[2];out->session=raw_u32(b+3);out->seq=raw_u16(b+7);out->time_ms=raw_u32(b+9);memcpy(out->data,b+13,out->length);return 1;
}
static int raw_newer(uint16_t seq,uint16_t old){return (int16_t)(seq-old)>0;}
static int raw_fresh(uint32_t now,uint32_t stamp){int32_t age=(int32_t)(now-stamp);return age>=-40&&age<=100;}
