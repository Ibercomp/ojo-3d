#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define GPIO_NUM_13 13
static int activo,seguimiento,follow_rest,control_source;
static int pca_ultimo[16],canales[3]={0,1,17};
static uint32_t direct_duty[2];
static int oe=1,running,starts,stops,valid_pca[16],duties[2];
static int pulses[3]={1560,1470,1810};
static void gpio_set_level(int pin,int value){
 assert(pin==13);
 if(!value){assert(valid_pca[0]==1560&&valid_pca[1]==1470);assert(running&&duties[1]==1810);}
 oe=value;
}
static void pwm_stop(unsigned mask){assert(mask==0&&oe);running=0;stops++;}
static void pwm_start(void){assert(duties[0]||duties[1]);running=1;starts++;}
static void pwm_set_duty(int channel,unsigned duty){duties[channel]=(int)duty;}
static void pca_write(int channel,int us){valid_pca[channel]=us;}
static void reset_curves(void){}
static int pulse(int i){return pulses[i];}
#include "../main/servo_output.h"
int main(void){
 all_off();assert(!activo&&!running&&oe&&starts==0);
 for(int k=0;k<100;k++){output_all();}
 assert(starts==0);
 power_on();assert(activo&&running&&!oe&&starts==1);
 int before=stops;
 for(int k=0;k<100;k++){power_on();}
 assert(starts==1&&stops==before);
 all_off();assert(!activo&&!running&&oe);
 power_on();assert(activo&&running&&!oe&&starts==2);
 all_off();assert(!running&&oe);
 puts("OK: boot/off keep PWM stopped; calibrated pulses before OE; idempotent enable.");
}
