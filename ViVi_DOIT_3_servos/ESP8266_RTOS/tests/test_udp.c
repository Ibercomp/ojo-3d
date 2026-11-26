#include <assert.h>
#include "../main/udp_protocol.h"
int main(void){
 uint8_t p[24]={0};memcpy(p,"OJ19",4);udp_put32(p+4,123);udp_put32(p+8,1);udp_put32(p+12,1000);udp_put16(p+16,5500);udp_put16(p+18,-2500);
 ojo_udp_session s={.token=123,.last_ms=1000};ojo_command c;
 assert(udp_decode(&s,p,24,1010,&c));assert(c.angle[0]==55&&c.angle[1]==-25);
 assert(!udp_decode(&s,p,24,1011,&c)); // duplicate
 udp_put32(p+8,0);assert(!udp_decode(&s,p,24,1011,&c));
 udp_put32(p+8,2);assert(!udp_decode(&s,p,24,1201,&c)); // stale
 assert(!udp_decode(&s,p,24,899,&c)); // future (also expired session)
 s=(ojo_udp_session){.token=123,.last_ms=1000};
 udp_put16(p+20,3300);assert(!udp_decode(&s,p,24,1020,&c));p[22]=1;assert(udp_decode(&s,p,24,1020,&c));
 udp_put32(p+8,3);p[23]=1;assert(!udp_decode(&s,p,24,1030,&c));p[23]=0;
 assert(!udp_decode(&s,p,23,1030,&c));
 assert(!udp_decode(&s,p,24,1721,&c));assert(!s.token);
 s=(ojo_udp_session){.token=123,.seq=UINT32_MAX,.last_ms=UINT32_MAX-10,.received=1};
 udp_put32(p+8,0);udp_put32(p+12,5);assert(udp_decode(&s,p,24,6,&c)); // wraps
 s.token=0;assert(!udp_decode(&s,p,24,7,&c)); // off/override invalidation
 return 0;
}
