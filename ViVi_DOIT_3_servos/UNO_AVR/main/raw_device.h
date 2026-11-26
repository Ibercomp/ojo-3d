#pragma once
#include "raw_protocol.h"
static uint32_t raw_session,target_stamp;
static uint16_t raw_sequence,bad_frames;
static uint8_t last_fault,pending_target;
static raw_packet pending;
static uint32_t raw_now(void){return now_frames()*20;}
static void raw_send(uint8_t type,uint16_t seq,const uint8_t*data,uint8_t len,uint32_t session){
 raw_packet p={.type=type,.length=len,.seq=seq,.session=session,.time_ms=raw_now()};memcpy(p.data,data,len);
 uint8_t wire[RAW_WIRE];size_t n=raw_encode(&p,wire);for(size_t i=0;i<n;i++)tx_putchar((char)wire[i],NULL);
}
static void raw_ack(const raw_packet*p,uint8_t status){uint8_t b[2]={status,p->type};raw_send(RAW_ACK,p->seq,b,2,p->session);}
static void raw_config(uint16_t seq){
 uint8_t b[48]={3,1,1,20};raw_put16(b+4,15);raw_put16(b+6,8000);
 for(int i=0;i<3;i++){raw_put16(b+8+2*i,centro[i]);b[14+i]=sentido[i];b[17+i]=9+i;}
 for(int i=0;i<7;i++){raw_put16(b+20+2*i,motion_limits.up[i]);raw_put16(b+34+2*i,motion_limits.down[i]);}
 raw_send(RAW_CONFIG,seq,b,sizeof(b),raw_session);
}
static void raw_telemetry(void){
 uint8_t b[24];for(int i=0;i<3;i++){raw_put16(b+2*i,(int16_t)lroundf(actual[i]*100));raw_put16(b+6+2*i,pulse(i));}
 raw_put16(b+12,(uint16_t)lroundf(follow_lid*100));
 b[14]=(activo?1:0)|(seguimiento?2:0)|(blink_phase?4:0)|(follow_rest?8:0)|(pending_target?16:0)|64;b[15]=last_fault;
 uint16_t errors;ATOMIC_BLOCK(ATOMIC_RESTORESTATE){errors=rx_errors;}
 raw_put16(b+16,errors);raw_put16(b+18,bad_frames);raw_put16(b+20,missed_ticks);
 int32_t age=(int32_t)(raw_now()-target_stamp);raw_put16(b+22,seguimiento?(age<0?0:age>65534?65534:(uint16_t)age):65535);
 raw_send(RAW_TELEMETRY,raw_sequence,b,sizeof(b),raw_session);
}
static void raw_apply_pending(void){
 if(!pending_target)return;
 pending_target=0;
 if(!activo||!raw_fresh(raw_now(),pending.time_ms))return;
 float a[3];for(int i=0;i<3;i++)a[i]=(int16_t)raw_u16(pending.data+2*i)*.01f;
 if(pending.data[6]&2){seguimiento=follow_rest=automatico=montaje=blink_phase=0;memcpy(objetivo,a,sizeof(a));}
 else{montaje=0;follow_set(a[0],a[1]);follow_lid=a[2];follow_rest=pending.data[6]&1;}
 target_stamp=pending.time_ms;
}
static void raw_receive(const raw_packet*p){
 // Any CRC-valid OFF is safe, including a foreign/expired session.
 if(p->type==RAW_ARM&&p->length==1&&p->data[0]==0){all_off();pending_target=0;raw_session=0;raw_sequence=0;raw_ack(p,0);return;}
 if(p->type==RAW_HELLO){
  if(p->length||!p->session){raw_ack(p,1);return;}if(activo){raw_ack(p,4);return;}
  all_off();pending_target=0;raw_session=p->session;raw_sequence=p->seq;last_fault=0;raw_config(p->seq);return;
 }
 if(!raw_session||p->session!=raw_session)return;
 if(!raw_newer(p->seq,raw_sequence)){if(p->type!=RAW_TARGET)raw_ack(p,5);return;}
 if(p->type!=RAW_STATE&&!raw_fresh(raw_now(),p->time_ms)){if(p->type!=RAW_TARGET)raw_ack(p,3);return;}
 if(p->type==RAW_TARGET){
  if(p->length!=7||!activo||(p->data[6]&~3))return;
  int16_t yaw=raw_u16(p->data),pitch=raw_u16(p->data+2);uint16_t lid=raw_u16(p->data+4);
  if(yaw< -5500||yaw>5500||pitch< -3500||pitch>3500||lid>((p->data[6]&1)?6000:3200))return;
  pending=*p;pending_target=1;raw_sequence=p->seq;ATOMIC_BLOCK(ATOMIC_RESTORESTATE){lease=35;}return;
 }
 ojo_command c;memset(&c,0,sizeof(c));int status=0;
 switch(p->type){
 case RAW_ARM:if(p->length!=1||p->data[0]!=1){status=1;break;}c.kind=OJO_ON;break;
 case RAW_STATE:if(p->length){status=1;break;}raw_sequence=p->seq;raw_telemetry();return;
 case RAW_CENTER:if(p->length){status=1;break;}c.kind=OJO_CENTER;break;
 case RAW_BLINK:if(p->length){status=1;break;}c.kind=OJO_BLINK;break;
 case RAW_LIMITS:
  if(p->length!=28){status=1;break;}c.kind=OJO_LIMITS;
  for(int i=0;i<7;i++){c.limits.up[i]=raw_u16(p->data+2*i);c.limits.down[i]=raw_u16(p->data+14+2*i);}
  if(!limits_valid(&c.limits))status=1;
  break;
 default:status=6;
 }
 if(!status){int code=execute(&c);status=code==200?0:code==409?2:1;}
 if(status){raw_ack(p,status);return;}
 raw_sequence=p->seq;if(p->type==RAW_CENTER)pending_target=0;
 if(p->type==RAW_ARM)last_fault=0;
 if(p->type==RAW_LIMITS)raw_config(p->seq);else raw_ack(p,0);
}
