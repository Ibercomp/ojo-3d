#define main animation_suite_main
#include "test_animacion.c"
#undef main
static int pca=1,control_source,ota_busy,montaje;
static void all_off(void){activo=0;seguimiento=0;follow_rest=0;control_source=0;reset_curves();}
static void power_on(void){all_off();activo=1;}
#include "../main/control_core.h"
int main(void){
 reset(0);automatico=0;follow_set(10,0);follow_lid=26;follow_blink_wait=100;
 animation_tick(.02f);assert(actual[0]>0 && !settled(2)); // partial lid does not freeze pursuit
 reset(0);automatico=0;follow_set(10,0);follow_lid=32;follow_rest=1;
 animation_tick(.02f);assert(actual[0]==0 && !settled(2)); // rest still waits for the lid

 reset(0);automatico=0;follow_set(20,0);follow_blink_wait=0;int blink_at=-1;
 for(int k=0;k<70;k++){follow_set(20+k*.4f,0);animation_tick(.02f);if(blink_phase){blink_at=k;break;}if(k<25)assert(!blink_phase);}
 assert(blink_at>=25&&blink_at<=55); // postpone pursuit blink, but never indefinitely
 reset(0);automatico=0;follow_set(0,0);follow_blink_wait=0;animation_tick(.02f);assert(blink_phase);

 reset(0);automatico=0;actual[0]=55;int early_pitch=0;
 for(int k=0;k<100;k++){follow_set(0,-25);follow_rest=1;animation_tick(.02f);
  assert(actual[1]>=-pitch_bound(actual[0],0)-.002f);
  if(actual[0]>35&&actual[1]<-.2f)early_pitch=1;
 }
 assert(early_pitch); // pitch must already move before yaw reaches its final corridor
 motion_limits_t original=motion_limits,candidate=motion_limits;candidate.up[6]=30;candidate.down[0]=20;
 assert(limits_valid(&candidate));motion_limits=candidate;
 assert(fabsf(pitch_bound(55,1)-3)<.001f);assert(fabsf(pitch_bound(-55,0)-2)<.001f);
 assert(fabsf(yaw_bound(3,1)-55)<.001f);
 reset(0);automatico=0;
 for(int k=0;k<20000;k++){
  if(k%19==0){follow_set((int)(esp_random()%151)-75,(int)(esp_random()%81)-40);follow_rest=1;follow_lid=0;}
  animation_tick(.02f);
  assert(actual[0]>=-55.001f&&actual[0]<=55.001f);
  assert(actual[1]<=pitch_bound(actual[0],1)+.002f&&actual[1]>=-pitch_bound(actual[0],0)-.002f);
 }
 motion_limits=original;reset(0);all_off();ojo_command c;
 const char*valid="/limites?up=0,150,250,250,250,150,30&down=0,150,250,250,250,150,0";
 assert(ojo_parse(valid,&c)==200);assert(execute_core(&c,1)==200);assert(motion_limits.up[6]==30);
 activo=1;assert(execute_core(&c,1)==409);activo=0;
 assert(ojo_parse("/limites?up=0,150,250,250,250,150,30&down=0,150,250,250,250,150",&c)==400);
 assert(ojo_parse("/limites?up=0,150,250,250,0,150,0&down=0,150,250,250,250,150,0",&c)==400);
 assert(ojo_parse("/limites?up=0,150,250,999,250,150,30&down=0,150,250,250,250,150,0",&c)==400);
 puts("OK: asymmetric envelopes, convex paths, atomic validation and motors-off calibration");return 0;
}
