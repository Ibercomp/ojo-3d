// Called under the motor mutex; shared by HTTP and UART. No I/O while locked.
#pragma once
#include "control_protocol.h"
static int execute_core(const ojo_command*c,int source){
 if(ota_busy)return 409;
 switch(c->kind){
 case OJO_STATE:return 200;
 case OJO_LIMITS:{
  if(activo||!limits_valid(&c->limits))return 409;
  motion_limits_t old=motion_limits;motion_limits=c->limits;
  if(fabsf(actual[1]-bounded_pitch(actual[1]))>.01f||fabsf(actual[0]-bounded_yaw(actual[0],actual[1]))>.01f){motion_limits=old;return 409;}
  break;
 }
 case OJO_ON:if(!pca)return 503;power_on();break;
 case OJO_OFF:all_off();automatico=0;blink_phase=0;break;
 case OJO_CENTER:seguimiento=0;follow_rest=0;objetivo[0]=objetivo[1]=objetivo[2]=0;blink_phase=0;automatico=montaje=0;break;
 case OJO_BLINK:if(!activo)return 409;blink_profile=0;start_blink();break;
 case OJO_MOVE:
  seguimiento=0;follow_rest=0;automatico=montaje=blink_phase=0;
  for(int i=0;i<3;i++){if(c->has[i]){objetivo[i]=limit(c->angle[i],i==0?-55:i==1?-35:0,i==0?55:i==1?35:max_apertura());}}
  break;
 case OJO_FOLLOW:
  if(!activo){return 409;}
  montaje=0;follow_set(c->angle[0],c->angle[1]);follow_lid=c->angle[2];follow_rest=c->rest;break;
 }
 control_source=source;return 200;
}

static void control_wifi_lost(void){if(control_source!=2){all_off();}}
