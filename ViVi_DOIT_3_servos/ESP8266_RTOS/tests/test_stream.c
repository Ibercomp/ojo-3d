#define main animation_suite_main
#include "test_animacion.c"
#undef main
int main(void){
 motion_stream s;float out[2];stream_reset(&s,.04,0,0);stream_push(&s,.04,4,2);stream_sample(&s,.06,out);assert(fabsf(out[0]-2)<.001f);
 stream_push(&s,.04,8,4);assert(s.count==2);stream_sample(&s,.06,out);assert(fabsf(out[0]-4)<.001f); // burst supersedes, never queued
 for(int k=0;k<100;k++)stream_push(&s,.1+k*.02f,k,k*.5f);
 assert(s.count==STREAM_CAPACITY);stream_sample(&s,10,out);assert(fabsf(out[0]-99)<.001f);
 reset(0);automatico=0;
 for(int k=0;k<100;k++){follow_set(k*.3f,0);follow_rest=1;animation_tick(.02f);check_limits();}
 for(int k=0;k<28;k++){float x=actual[0];animation_tick(.02f);assert(fabsf(actual[0]-x)<=1.601f);check_limits();}
 assert(follow_stale && seguimiento);assert(fabsf(velocidad[0])<1.0f);float stopped=actual[0];
 // A delivery burst after 560 ms must not directly change the pose or replay old targets.
 follow_set(50,0);follow_set(-40,0);follow_set(10,0);assert(actual[0]==stopped);assert(follow_stream.count==2);
 float v=velocidad[0];animation_tick(.02f);assert(fabsf(velocidad[0]-v)<=14.01f);assert(fabsf(actual[0]-stopped)<.5f);
 for(int k=0;k<200;k++){follow_set(10,0);follow_rest=1;animation_tick(.02f);check_limits();}
 assert(fabsf(actual[0]-10)<.02f);
 for(int k=0;k<80;k++){animation_tick(.02f);check_limits();}assert(!seguimiento);
 stopped=actual[0];for(int k=0;k<50;k++)animation_tick(.02f);assert(actual[0]==stopped);
 reset(0);automatico=0;
 for(int k=0;k<10000;k++){
  if(k%9==0){follow_set(-55,25);follow_set(55,-25);follow_set(k%18?55:-55,k%27?25:-25);follow_rest=1;}
  float old[2]={actual[0],actual[1]};animation_tick(.02f);check_limits();
  for(int i=0;i<2;i++)assert(fabsf(actual[i]-old[i])<=1.601f);
 }
 printf("OK: fixed-delay interpolation, bounded burst, gap braking, recovery and TTL\n");return 0;
}
