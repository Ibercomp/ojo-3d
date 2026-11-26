// cc -std=c99 -Wall -Wextra tests/test_animacion.c -lm -o test_animacion
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <assert.h>
static int activo=1, automatico=1, max_lid=60;
static uint32_t seed=12345;
static uint32_t esp_random(void){seed=1664525*seed+1013904223;return seed^(seed>>13);}
static float limit(float x,float a,float b){return x<a?a:x>b?b:x;}
static int max_apertura(void){return max_lid;}
#include "../main/animacion.h"

static void reset(int patron){
 memset(actual,0,sizeof(actual));memset(objetivo,0,sizeof(objetivo));
 reset_curves();blink_phase=blink_profile=seguimiento=0;blink_wait=0;
 demo_phase=demo_ticks=demo_escena=demo_paso=natural_blink_ticks=0;
 demo_patron=patron;demo_x=demo_y=0;activo=automatico=1;
}
static void check_limits(void){
 for(int i=0;i<3;i++)assert(isfinite(actual[i])&&isfinite(velocidad[i]));
 assert(fabsf(actual[0])<=yaw_limit(actual[1])+0.001f);
 assert(fabsf(actual[1])<=25.001f);
 assert(actual[2]>=-0.001f && actual[2]<=max_lid+0.001f);
}
static void patterns(void){
 for(int pat=0;pat<12;pat++){
  if(pat==1)continue;
  reset(pat);int blinks=0,moves=0,squints=0,closing=0,first_close=0;
  float close_time=0,cycle_time=0,first_cycle=0;
  for(int k=0;k<15000;k++){
   float x=actual[0],y=actual[1];int bp=blink_phase,dp=demo_phase;
   animation_tick(0.02f);check_limits();
   if(!bp&&blink_phase){blinks++;closing=1;close_time=cycle_time=0;}
   if(blink_phase)cycle_time+=0.02f;
   if(closing)close_time+=0.02f;
   if(closing&&blink_phase==2){if(!first_close){first_close=1;printf("%s cierre=%.0f ms ",patron_nombre(pat),1000*close_time);}closing=0;}
   if(bp&&!blink_phase&&!first_cycle){first_cycle=cycle_time;printf("ciclo=%.0f ms\n",1000*cycle_time);}
   if(bp&&blink_phase){assert(fabsf(actual[0]-x)<0.001f);assert(fabsf(actual[1]-y)<0.001f);}
   if(dp!=1&&demo_phase==1)moves++;
   if(dp!=3&&demo_phase==3)squints++;
   if(demo_phase==3||demo_phase==4){assert(fabsf(actual[1])<0.021f);assert(fabsf(velocidad[0])<0.1f);}
   if(demo_phase==1&&!blink_phase){
    if(demo_escena==11){assert(fabsf(actual[2]-fminf(32,max_lid))<.021f);assert(fabsf(actual[1])<.021f);}
    else assert(actual[2]<0.021f);
   }
   if(pat==0 && demo_phase)assert(demo_escena==8||demo_escena==4||demo_escena==11);
  }
  assert(pat!=4||squints>5);
  assert(pat<5||pat==9||moves>5);
  assert(pat==4||blinks>5);
  if(pat==2||pat==3||pat==9)assert(first_cycle>0.3f&&first_cycle<0.65f);
  printf("%s: %d miradas, %d parpadeos, %d sospechas / 300 s\n",patron_nombre(pat),moves,blinks,squints);
 }
}
static void manual_and_interruptions(void){
 reset(0);automatico=0;
 for(int k=0;k<40000;k++){
  if(k%19==0){
   objetivo[0]=(int)(esp_random()%111)-55;objetivo[1]=(int)(esp_random()%51)-25;
   objetivo[2]=esp_random()%(max_lid+1);blink_phase=0;
  }
  animation_tick(k%7==0?0.04f:0.02f);check_limits();
 }
 reset(0);automatico=0;objetivo[0]=35;objetivo[1]=25;
 for(int k=0;k<300;k++)animation_tick(0.02f);
 assert(fabsf(actual[0]-30)<0.01f&&fabsf(actual[1]-25)<0.01f);
 // Interrumpir movimiento con parpadeo, congelar globo y volver a abrir.
 objetivo[0]=-30;animation_tick(0.02f);start_blink();
 float x=actual[0],y=actual[1];int steps=0;
 while(blink_phase&&steps++<100){animation_tick(0.02f);assert(fabsf(actual[0]-x)<0.001f&&fabsf(actual[1]-y)<0.001f);}
 assert(!blink_phase&&actual[2]==0);
 activo=0;objetivo[0]=-35;float before=actual[0];animation_tick(0.02f);assert(actual[0]==before);
}
static void smooth_stops(void){
 reset(0);automatico=0;objetivo[0]=20;objetivo[1]=10;
 float last=0,prior_speed=0;int steps=0;
 do{
  prior_speed=velocidad[0];animation_tick(0.02f);
  assert(actual[0]>=last-0.0001f&&actual[0]<=20.0001f);
  assert(fabsf(actual[1]-actual[0]*0.5f)<0.002f);
  last=actual[0];steps++;
 }while(!settled(0)&&steps<100);
 assert(steps<100&&fabsf(prior_speed)<16);
}
static void camera_follow(void){
 reset(0);automatico=0;max_lid=60;
 follow_set(35,25);
 for(int k=0;k<600;k++){
  if(k%3==0)follow_set(35*sinf(k*0.01f),25*cosf(k*0.01f));
  float x=actual[0],y=actual[1];int bp=blink_phase;
  animation_tick(0.02f);check_limits();
  if(bp&&blink_phase){assert(fabsf(actual[0]-x)<0.001f&&fabsf(actual[1]-y)<0.001f);}
 }
 // Dejar de recibir ordenes: parar, sin volver al automatico ni al centro.
 for(int k=0;k<40;k++)animation_tick(0.02f);
 assert(!seguimiento&&!automatico);
 float x=actual[0],y=actual[1];
 for(int k=0;k<100;k++)animation_tick(0.02f);
 assert(fabsf(actual[0]-x)<0.001f&&fabsf(actual[1]-y)<0.001f);
 // Blink manual durante seguimiento; ultima orden reemplaza a las anteriores.
 follow_set(-20,0);start_blink();x=actual[0];y=actual[1];int n=0;
 while(blink_phase&&n++<100){
  follow_set(20,10);animation_tick(0.02f);
  if(blink_phase)assert(fabsf(actual[0]-x)<0.001f&&fabsf(actual[1]-y)<0.001f);
 }
 assert(n<100);
 for(int k=0;k<100;k++){follow_set(20,10);animation_tick(0.02f);}
 assert(fabsf(actual[0]-20)<0.01f&&fabsf(actual[1]-10)<0.01f);
}
static void streaming_response(void){
 reset(0);automatico=0;follow_set(25,0);animation_tick(.02f);
 assert(velocidad[0]<=60.01f && actual[0]<=.601f);

 reset(0);automatico=0;actual[0]=-20;
 float sum=0;int n=0;
 for(int k=0;k<50;k++){
  float target=-20+40*k*.02f;
  follow_set(target,0);follow_blink_wait=100;animation_tick(.02f);
  check_limits();assert(fabsf(velocidad[0])<=160.001f);
  if(k>10){sum+=target-actual[0];n++;}
 }
 printf("stream lag: %.3f deg at 40 deg/s\n",sum/n);
 assert(sum/n<3.6f); // Includes the explicit 40 ms interpolation window.
 for(int k=0;k<1500;k++){
  if(k%11==0)follow_set((k%22)?-35:35,(k%33)?25:-25);
  follow_ttl=.7f;follow_blink_wait=100;animation_tick(k%5==0?.04f:.02f);
  check_limits();
  assert(fabsf(velocidad[0])<=160.001f && fabsf(velocidad[1])<=160.001f);
 }
}
static void curious_follow(void){
 reset(0);automatico=0;max_lid=60;follow_set(10,5);follow_lid=22;
 for(int k=0;k<70;k++){follow_set(10,5);follow_blink_wait=100;animation_tick(.02f);check_limits();}
 assert(fabsf(actual[2]-22)<.01f);assert(fabsf(actual[0]-10)<.01f);
 start_blink();int n=0;float x=actual[0],y=actual[1];
 while(blink_phase && n++<100){follow_set(15,5);animation_tick(.02f);
  if(blink_phase){assert(fabsf(actual[0]-x)<.001f);assert(fabsf(actual[1]-y)<.001f);}}
 assert(n<100);
 // Expiring curiosity during the closed phase must reopen directly to 0,
 // not pause at the old squint and then open a second time.
 start_blink();follow_lid=0;n=0;
 while(blink_phase!=3 && n++<100){follow_set(15,5);animation_tick(.02f);}
 assert(blink_phase==3 && objetivo[2]==0);
 // Moving face: reopen and resume, preserving the calibrated mechanical limits.
 follow_lid=0;
 for(int k=0;k<70;k++){follow_set(15,5);animation_tick(.02f);check_limits();}
 assert(actual[2]<.01f && fabsf(actual[0]-15)<.01f);
 follow_lid=16;
 for(int k=0;k<100;k++){animation_tick(.02f);check_limits();}
 assert(!seguimiento && actual[2]<.01f);
}
static void blink_asymmetry(void){
 reset(0);automatico=0;max_lid=60;start_blink();
 float close=0,open=0,last_speed=0,peak=0,penultimate=0;
 int n=0;
 while(blink_phase && n++<100){
  int phase=blink_phase;
  if(phase==1)close+=.02f;
  if(phase==3){open+=.02f;penultimate=last_speed;last_speed=fabsf(velocidad[2]);peak=fmaxf(peak,last_speed);}
  animation_tick(.02f);check_limits();
 }
 assert(n<100 && close<=.22f && open>close);
 assert(actual[2]==0 && velocidad[2]==0);
 assert(last_speed<peak*.15f && penultimate<peak*.35f);
 printf("Parpadeo: cierre %.0f ms, apertura %.0f ms; frenado final verificado\n",close*1000,open*1000);
}
static void extended_horizontal_envelope(void){
 assert(yaw_limit(0)==55 && yaw_limit(15)==45 && yaw_limit(20)==37.5f && yaw_limit(25)==30);
 for(int side=-1;side<=1;side+=2){
  reset(0);automatico=0;
  for(int k=0;k<200;k++){follow_set(side*55,0);follow_rest=1;animation_tick(.02f);check_limits();}
  assert(fabsf(actual[0]-side*55)<.02f);
  for(int k=0;k<200;k++){follow_set(side*55,25);follow_rest=1;animation_tick(.02f);check_limits();}
  assert(fabsf(actual[0]-side*30)<.02f && fabsf(actual[1]-25)<.02f);
  // Following a lateral target must be able to leave the diagonal stop:
  // center pitch first, unlocking horizontal travel without crossing the envelope.
  for(int k=0;k<200;k++){follow_set(side*55,0);follow_rest=1;animation_tick(.02f);check_limits();}
  assert(fabsf(actual[0]-side*55)<.02f && fabsf(actual[1])<.02f);
 }
}
static void squinted_search_follow(void){
 reset(0);automatico=0;max_lid=60;
 int blinks=0;float left=0,right=0;
 for(int k=0;k<1800;k++){
  follow_set(k%400<200?-55:55,0);follow_lid=32;
  int bp=blink_phase;float x=actual[0];
  animation_tick(.02f);check_limits();
  if(!bp&&blink_phase)blinks++;
  if(bp&&blink_phase)assert(fabsf(actual[0]-x)<.001f);
  if(!blink_phase&&settled(2)){left=fminf(left,actual[0]);right=fmaxf(right,actual[0]);assert(fabsf(actual[2]-32)<.021f);}
 }
 assert(left < -54.9f && right > 54.9f && blinks>=3);
}
int main(void){
 setbuf(stdout,NULL);
 assert(patron_id("lento")==-1&&patron_id("")==-1);
 assert(patron_id("medio")==patron_id("natural"));
 extended_horizontal_envelope();squinted_search_follow();patterns();manual_and_interruptions();smooth_stops();
 max_lid=40;manual_and_interruptions();
 camera_follow();streaming_response();curious_follow();blink_asymmetry();
 puts("OK: limites, fijaciones, cierre rapido, parada suave y comandos interrumpidos.");return 0;
}
