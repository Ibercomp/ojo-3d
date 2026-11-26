// Motor compartido por el firmware y las pruebas de trayectorias en el host.
// Unidades: grados del mecanismo, segundos. PWM y control: 50 Hz.
#pragma once
#include "motion_limits.h"
#include "motion_stream.h"

static float objetivo[3], actual[3], velocidad[3];
static int blink_phase, blink_profile;
static float blink_restore, blink_wait, blink_close_speed, blink_open_speed;
static int demo_phase, demo_ticks, demo_patron, demo_escena, demo_paso;
static int demo_total, natural_blink_ticks;
static float demo_x, demo_y;
static int seguimiento, follow_rest;
static float follow_target[2], follow_ttl, follow_blink_wait, follow_lid, follow_still, follow_still_need;

typedef struct {
 float from, to, elapsed, duration, tangent;
 int valid;
} motion_curve;
static motion_curve curvas[3];
static motion_stream follow_stream;
static double follow_clock,follow_received;
static int follow_stale;
static float follow_resume_s,follow_accel[2];

static void reset_curves(void){
 for(int i=0;i<3;i++){curvas[i].valid=0;velocidad[i]=0;}
 follow_accel[0]=follow_accel[1]=0;
}
static void hold_gaze(void){
 for(int i=0;i<2;i++){objetivo[i]=actual[i];velocidad[i]=0;curvas[i].valid=0;}
}
static int settled(int i){return fabsf(actual[i]-objetivo[i])<0.02f && fabsf(velocidad[i])<0.1f;}
static float yaw_limit(float pitch){return 55.0f-2.0f*fminf(fabsf(pitch),15.0f)/3.0f-1.5f*limit(fabsf(pitch)-15.0f,0,10);}

static void smooth_axis(int i,float dst,float dt){
 motion_curve *c=&curvas[i];
 if(!c->valid || fabsf(c->to-dst)>0.001f){
  float distance=fabsf(dst-actual[i]);
  float vmax=i==2?(blink_phase==1?blink_close_speed:blink_phase==3?blink_open_speed:140.0f):80.0f;
  // Quintica: velocidad y aceleracion cero al finalizar, sin recorte al llegar.
  float duration=fmaxf(i==2?(blink_phase==1?0.14f:0.18f):0.16f,1.875f*distance/vmax);
  // Las dos componentes de una mirada terminan juntas.
  if(i<2){
   float dx=fabsf(transition_yaw(objetivo[0],actual[1],objetivo[1])-actual[0]);
   float dy=fabsf(objetivo[1]-actual[1]);
   duration=fmaxf(duration,1.875f*fmaxf(dx,dy)/vmax);
   if(i==1 && curvas[0].valid && curvas[0].elapsed<=dt+0.001f)
    duration=fmaxf(duration,curvas[0].duration);
  }
  *c=(motion_curve){.from=actual[i],.to=dst,.duration=duration,.valid=1};
  // Conservar velocidad al retarget manual cuando permite una curva monotona.
  float delta=dst-actual[i];
  c->tangent=copysignf(limit(velocidad[i]*copysignf(1,delta)*duration,0,2*fabsf(delta)),delta);
 }
 c->elapsed=fminf(c->elapsed+dt,c->duration);
 float t=c->elapsed/c->duration, d=c->to-c->from, v=c->tangent;
 float a=10*d-6*v,b=-15*d+8*v,e=6*d-3*v;
 actual[i]=c->from+t*(v+t*t*(a+t*(b+t*e)));
 velocidad[i]=(v+t*t*(3*a+t*(4*b+t*5*e)))/c->duration;
 if(c->elapsed>=c->duration){actual[i]=dst;velocidad[i]=0;}
}

// Streaming camera targets must preserve velocity instead of restarting a
// point-to-point quintic for every packet. Exact critically damped integration.
static void follow_axis(int i,float dst,float dt){
 const float omega=45.0f, max_speed=80.0f;
 float x=actual[i],v=velocidad[i];
 // Ramp the allowed pursuit speed only on start/recovery. Preserve the current
 // velocity: changing targets must never be interpreted as a completed move.
 float ramp=follow_resume_s>0?limit(1.0f-follow_resume_s/.30f,0,1):1;
 float vmax=fmaxf(fabsf(v),max_speed*(.10f+.90f*ramp));
 float change=limit(x-dst,-2.0f*vmax/omega,2.0f*vmax/omega);
 float target=x-change,decay=expf(-omega*dt);
 float temp=(v+omega*change)*dt;
 float next=target+(change+temp)*decay;
 float next_v=(v-omega*temp)*decay;
 // Exact critically damped state integration. The old acceleration/jerk patch
 // mixed two integrators and snapped velocity to zero at a moving target,
 // creating repeated stop/restart cycles even for a constant-speed input.
 if(fabsf(dst-x)<.0001f && fabsf(v)<.001f){next=dst;next_v=0;}
 follow_accel[i]=(next_v-v)/dt; // Measured model acceleration, not a fake bound.
 actual[i]=next;velocidad[i]=next_v;curvas[i].valid=0;
}

static void start_blink(void){
 if(blink_phase)return;
 hold_gaze();
 blink_restore=objetivo[2];objetivo[2]=max_apertura();
 // Cierre mas rapido que apertura. Ningun perfil produce un parpadeo lento.
 blink_close_speed=blink_profile==3?750.0f:650.0f+(esp_random()%41);
 blink_open_speed=blink_profile==3?410.0f:360.0f+(esp_random()%41);
 blink_phase=1;blink_wait=0;curvas[2].valid=0;
}
static int patron_id(const char *s){
 const char *n[]={"mezcla","","natural","rapido","enfadado","lado","mareado","repaso","curioso","doble","atento","busqueda"};
 if(!strcmp(s,"medio"))return 2; // Compatibilidad: tambien es rapido y suave.
 for(int i=0;i<12;i++)if(n[i][0]&&!strcmp(s,n[i]))return i;
 return -1;
}
static const char *patron_nombre(int p){
 static const char *n[]={"mezcla","","natural","rapido","enfadado","lado","mareado","repaso","curioso","doble","atento","busqueda"};
 return p>=0&&p<12&&p!=1?n[p]:"mezcla";
}
static void next_blink(void){natural_blink_ticks=130+(int)(esp_random()%170);}
static void follow_set(float yaw,float pitch){
 int reset_stream=!seguimiento || follow_clock-follow_received>STREAM_STALE;
 if(reset_stream){stream_reset(&follow_stream,follow_clock,actual[0],actual[1]);follow_resume_s=.30f;follow_accel[0]=follow_accel[1]=0;follow_stale=0;}
 if(!seguimiento){
  follow_lid=0;follow_rest=0;follow_still=0;follow_still_need=.4f;
  follow_blink_wait=3.0f+(esp_random()%300)/100.0f;
  hold_gaze();
 }
 seguimiento=1;automatico=0;follow_ttl=0.7f;
 follow_target[1]=bounded_pitch(pitch);
 follow_target[0]=bounded_yaw(yaw,follow_target[1]);
 follow_received=follow_clock;
 stream_push(&follow_stream,follow_clock,follow_target[0],follow_target[1]);
 // Una consigna nueva nunca cancela un parpadeo; queda como ultima consigna.
}
static void follow_step(float dt){
 if(!seguimiento)return;
 follow_ttl-=dt;
 if(follow_ttl<=0){seguimiento=0;follow_lid=0;objetivo[2]=0;hold_gaze();return;}
 if(blink_phase)return;
 if(follow_clock-follow_received>STREAM_STALE){
  if(!follow_stale){
   float stop[2];for(int i=0;i<2;i++)stop[i]=actual[i]+copysignf(velocidad[i]*velocidad[i]/600.0f,velocidad[i]);
   objetivo[1]=bounded_pitch(stop[1]);objetivo[0]=bounded_yaw(stop[0],objetivo[1]);follow_stale=1;follow_resume_s=.30f;
  }
  return;
 }
 objetivo[2]=limit(follow_lid,0,fminf(follow_rest?60:32,max_apertura()));
 if(!settled(2)&&follow_rest){hold_gaze();return;}
 float sampled[2];stream_sample(&follow_stream,follow_clock,sampled);
 if(follow_rest){objetivo[0]=sampled[0];objetivo[1]=sampled[1];return;}
 follow_blink_wait-=dt;
 int pursuing=fmaxf(fabsf(velocidad[0]),fabsf(velocidad[1]))>12.0f || fmaxf(fabsf(follow_target[0]-actual[0]),fabsf(follow_target[1]-actual[1]))>2.0f;
 // Blink only during fixation: never while pursuing. After fast motion the
 // eye must stay still longer before blinking.
 if(pursuing){follow_still=0;if(fmaxf(fabsf(velocidad[0]),fabsf(velocidad[1]))>40.0f)follow_still_need=.8f;}
 else follow_still+=dt;
 if(follow_blink_wait<=0 && follow_still>=follow_still_need){
  blink_profile=2;start_blink();follow_blink_wait=3.0f+(esp_random()%300)/100.0f;follow_still_need=.4f;return;
 }
 objetivo[0]=sampled[0];objetivo[1]=sampled[1];
}
static void demo_goto(void){
 static const float circular[][2]={{55,0},{25,18},{0,25},{-25,18},{-55,0},{-25,-18},{0,-25},{25,-18},{55,0}};
 if(demo_escena==5||demo_escena==11){static const float x[]={-55,55,-55,0};objetivo[0]=x[demo_paso];objetivo[1]=0;}
 else if(demo_escena==6){objetivo[0]=circular[demo_paso][0];objetivo[1]=circular[demo_paso][1];}
 else if(demo_escena==7){static const float y[]={25,-25,25,0};objetivo[0]=limit(demo_x,-30,30);objetivo[1]=y[demo_paso];}
 else if(demo_paso==0){
  // Elegir un punto de interes; no barrer continuamente todo el recorrido.
  if(demo_escena==10){demo_x=actual[0];demo_y=actual[1];}
  else{
   int amplio=esp_random()%8==0;
   demo_x=(int)(esp_random()%(amplio?67:45))-(amplio?33:22);
   demo_y=(int)(esp_random()%29)-14;
  }
  objetivo[0]=demo_x;objetivo[1]=demo_y;
 }else{
  // Reajustes perceptibles en el PCA (evitar temblor subresolucion).
  objetivo[0]=demo_x+(int)(esp_random()%7)-3;
  objetivo[1]=demo_y+(int)(esp_random()%5)-2;
 }
 objetivo[1]=bounded_pitch(objetivo[1]);
 objetivo[0]=bounded_yaw(objetivo[0],objetivo[1]);
 objetivo[2]=demo_escena==11?fminf(32,max_apertura()):0;demo_phase=1;
}
static void demo_step(void){
 if(!activo||!automatico)return;
 if(natural_blink_ticks>0)natural_blink_ticks--;
 // Parpadeo intercalado en una fijacion, sin perder el punto observado.
 if(demo_phase==9){if(!blink_phase){next_blink();demo_phase=2;}return;}
 if(demo_phase==5){
  if(!blink_phase){
   next_blink();
   if(demo_escena==9 && demo_paso==0){demo_paso=1;demo_ticks=7;demo_phase=8;}
   else {demo_ticks=70+(int)(esp_random()%80);demo_phase=7;}
  }
  return;
 }
 if(blink_phase)return; // Tambien protege un parpadeo pedido desde la web.
 if(demo_phase==8){if(--demo_ticks<=0){blink_profile=3;start_blink();demo_phase=5;}return;}
 if(demo_phase==7){if(--demo_ticks<=0)demo_phase=0;return;}
 if(demo_phase==0){
  hold_gaze();objetivo[2]=0;
  if(settled(2)){
   // Alternar inspeccion natural, desconfianza y busqueda entrecerrada.
   demo_escena=demo_patron?demo_patron:(esp_random()%6==0?11:esp_random()%12==0?4:8);
   demo_paso=0;demo_x=actual[0];demo_y=actual[1];
   demo_total=demo_escena==6?9:demo_escena==8?2+(int)(esp_random()%3):demo_escena==10?3:4;
   if(!natural_blink_ticks)next_blink();
   if(demo_escena==2||demo_escena==3||demo_escena==9){blink_profile=demo_escena==2?2:3;start_blink();demo_phase=5;}
   else if(demo_escena==4){objetivo[1]=0;demo_phase=6;}
   else if(demo_escena==11){objetivo[1]=0;demo_phase=10;}
   else demo_goto();
  }
 }else if(demo_phase==10){
  if(settled(0)&&settled(1)){objetivo[2]=fminf(32,max_apertura());demo_phase=11;}
 }else if(demo_phase==11){
  if(settled(2))demo_goto();
 }else if(demo_phase==6){
  if(settled(0)&&settled(1)){
   hold_gaze();objetivo[1]=0;
   objetivo[2]=limit(24+(int)(esp_random()%13),0,max_apertura());demo_phase=3;
  }
 }else if(demo_phase==1){
  if(settled(0)&&settled(1)){
   // Fijaciones desiguales: mirar algo, inspeccionarlo y cambiar de interes.
   demo_ticks=demo_escena==6?2:demo_escena==10?75+(int)(esp_random()%100):
    demo_paso==0?30+(int)(esp_random()%75):12+(int)(esp_random()%35);
   demo_phase=2;
  }
 }else if(demo_phase==2){
  if(natural_blink_ticks<=0){blink_profile=2;start_blink();demo_phase=9;return;}
  if(--demo_ticks<=0){
   if(++demo_paso<demo_total)demo_goto();
   else {demo_ticks=8+(int)(esp_random()%25);demo_phase=7;}
  }
 }else if(demo_phase==3){
  if(settled(2)){demo_ticks=35+(int)(esp_random()%55);demo_phase=4;}
 }else if(demo_phase==4 && --demo_ticks<=0){objetivo[2]=0;demo_phase=0;}
}
static void animation_tick(float dt){
 follow_clock+=dt;
 if(follow_resume_s>0)follow_resume_s=fmaxf(0,follow_resume_s-dt);
 if(!activo)return;
 float previous_gaze[2]={actual[0],actual[1]};
 objetivo[2]=limit(objetivo[2],0,max_apertura());
 if(blink_phase==1 && settled(2)){blink_phase=2;blink_wait=0.02f;}
 else if(blink_phase==2){
  blink_wait-=dt;
  if(blink_wait<=0){objetivo[2]=limit(seguimiento?follow_lid:blink_restore,0,max_apertura());blink_phase=3;}
 }else if(blink_phase==3 && settled(2))blink_phase=0;
 follow_step(dt);demo_step();
 objetivo[1]=bounded_pitch(objetivo[1]);
 float destino_yaw=transition_yaw(objetivo[0],actual[1],objetivo[1]),destino_pitch=objetivo[1];
 // Follow the available boundary continuously instead of holding all pitch
 // until the complete requested elevation fits at the current yaw.
 destino_pitch=limit(destino_pitch,-pitch_bound(actual[0],0),pitch_bound(actual[0],1));
 if(seguimiento && !blink_phase && (settled(2)||!follow_rest)){
  follow_axis(0,destino_yaw,dt);follow_axis(1,destino_pitch,dt);
 }else{smooth_axis(0,destino_yaw,dt);smooth_axis(1,destino_pitch,dt);}
 smooth_axis(2,objetivo[2],dt);
 float permitido=bounded_yaw(actual[0],actual[1]);
 if(fabsf(actual[0]-permitido)>0.0001f){actual[0]=permitido;velocidad[0]=0;curvas[0].valid=0;}
 // Absolute output slew cap, including manual/search curves and envelope edges.
 float extent=fmaxf(fabsf(actual[0]-previous_gaze[0]),fabsf(actual[1]-previous_gaze[1]));
 if(extent>80.0f*dt){float k=80.0f*dt/extent;for(int i=0;i<2;i++){actual[i]=previous_gaze[i]+(actual[i]-previous_gaze[i])*k;velocidad[i]=(actual[i]-previous_gaze[i])/dt;}}
}
