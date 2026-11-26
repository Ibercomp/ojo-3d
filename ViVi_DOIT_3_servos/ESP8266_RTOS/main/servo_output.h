// Hardware output lifecycle. Shared with a host test using instrumented drivers.
#pragma once
static void all_off(void){
 // Gate the PCA first, then stop the direct PWM timer and force its pins low.
 // A zero duty update is asynchronous; pwm_stop is an immediate stop.
 gpio_set_level(GPIO_NUM_13,1);
 pwm_stop(0);
 activo=0;seguimiento=0;follow_rest=0;control_source=0;
 direct_duty[0]=direct_duty[1]=0;
 for(int i=0;i<16;i++){pca_ultimo[i]=-1;pca_write(i,0);}
 reset_curves();
}
static void output_all(void){
 if(!activo)return;
 uint32_t d[2]={0,0};
 for(int i=0;i<3;i++){
  int c=canales[i],us=pulse(i);
  if(c>=0&&c<16)pca_write(c,us);
  else if(c>=16&&c<18)d[c-16]=us;
 }
 if(d[0]!=direct_duty[0]||d[1]!=direct_duty[1]){
  memcpy(direct_duty,d,sizeof(d));
  pwm_set_duty(0,d[0]);pwm_set_duty(1,d[1]);
  if(d[0]||d[1])pwm_start();else pwm_stop(0);
 }
}
static void power_on(void){
 if(activo)return; // Repeated activation must not cycle the outputs.
 all_off();activo=1;
 output_all(); // Prepare valid calibrated pulses before enabling the PCA.
 gpio_set_level(GPIO_NUM_13,0);
}
