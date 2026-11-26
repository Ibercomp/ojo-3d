// Regression: a steadily moving reference must not repeatedly stop the motor.
#define main animation_suite_main
#include "test_animacion.c"
#undef main
int main(void){
 reset(0);automatico=0;follow_clock=follow_received=0;
 float previous=actual[0],vmin=1e9f,vmax=-1e9f;
 for(int k=0;k<150;k++){
  follow_set(k*.3f,0);follow_lid=0;follow_rest=1;animation_tick(.02f);check_limits();
  float speed=(actual[0]-previous)/.02f;previous=actual[0];
  if(k>=25){vmin=fminf(vmin,speed);vmax=fmaxf(vmax,speed);assert(speed>14.9f&&speed<15.1f);assert(velocidad[0]>10);}
 }
 for(int k=0;k<150;k++){follow_set(45,0);follow_rest=1;animation_tick(.02f);check_limits();assert(actual[0]<=45.001f);}
 assert(fabsf(actual[0]-45)<.01f);
 // Direction changes preserve the position state and mechanical slew bound.
 for(int k=0;k<300;k++){float old=actual[0];follow_set(k<100?-20:k<200?20:0,0);follow_rest=1;animation_tick(.02f);check_limits();assert(fabsf(actual[0]-old)<=1.601f);}
 printf("OK: 15 deg/s reference -> output %.4f..%.4f deg/s; no periodic stop/restart.\n",vmin,vmax);
}
