#include <assert.h>
#include <stdio.h>
#include "../main/raw_protocol.h"
int main(void){
 assert(raw_crc((const uint8_t*)"123456789",9)==0x29b1);
 for(int n=0;n<=48;n++){
  raw_packet p={.type=RAW_TARGET,.length=n,.session=0x12345678,.seq=65535,.time_ms=0xfffffff0};
  for(int i=0;i<n;i++)p.data[i]=(uint8_t)(i*5);
  uint8_t wire[RAW_WIRE];size_t length=raw_encode(&p,wire);assert(length==(size_t)n+17);
  raw_decoder d={0};raw_packet q;int result=0;
  for(size_t i=0;i<length;i++){result=raw_feed(&d,wire[i],&q);if(i+1<length)assert(!result);}
  assert(result==1&&q.type==p.type&&q.length==n&&q.seq==p.seq&&q.time_ms==p.time_ms&&q.session==p.session&&!memcmp(q.data,p.data,n));
  for(size_t i=0;i<length-1;i++)for(int bit=0;bit<8;bit++){
   raw_decoder bad={0};int accepted=0;for(size_t j=0;j<length;j++){uint8_t b=wire[j]^(j==i?1<<bit:0);if(raw_feed(&bad,b,&q)>0)accepted++;}assert(!accepted);
  }
 }
 assert(raw_newer(0,65535)&&!raw_newer(65535,0)&&!raw_newer(1,1));
 assert(raw_fresh(10,0xfffffff0)&&!raw_fresh(1000,899)&&!raw_fresh(1000,1041));
 raw_decoder d={0};raw_packet q;for(int i=0;i<200;i++)assert(!raw_feed(&d,9,&q));assert(raw_feed(&d,0,&q)==-1);
 raw_packet p={.type=RAW_TARGET,.length=7,.session=0x12345678,.seq=42,.time_ms=1000};raw_put16(p.data,-1234);raw_put16(p.data+2,567);raw_put16(p.data+4,3200);p.data[6]=1;
 uint8_t wire[RAW_WIRE];size_t n=raw_encode(&p,wire);printf("GOLDEN ");for(size_t i=0;i<n;i++)printf("%02x",wire[i]);puts("");
 for(size_t i=0;i<n;i++)assert(raw_feed(&d,wire[i],&q)==(i+1==n?1:0));
 puts("OK: COBS, CRC, all sizes, every single-bit corruption, overflow/resync, sequence/time wrap.");
}
