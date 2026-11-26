// ATmega328P / Uno R3. Native avr-libc; no Arduino core or Servo library.
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/pgmspace.h>
#include <avr/eeprom.h>
#include <avr/wdt.h>
#include <util/atomic.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <errno.h>
#define strtof strtod
#define RX_SIZE 128
// Servo outputs on PORTD: D2 yaw, D3 pitch, D4 lid (D9-D13 belong to the Wi-Fi
// module on the Nano PCB and are left as inputs). All three pulses are made in
// software and timed against Timer1 (0.5 us ticks).
#define PIN_BITS {_BV(PD2),_BV(PD3),_BV(PD4)}
#define PINS (_BV(PD2)|_BV(PD3)|_BV(PD4))
static volatile uint8_t activo, lease, fault, hardware_fault;
static volatile uint32_t frames;
static volatile uint16_t pulse_us[3]={1560,1470,1810}, rx_errors, lost_link;
static volatile uint8_t rx[RX_SIZE], rx_head, rx_tail;
static uint16_t edge_end[3];static uint8_t edge_bit[3],edge_count,edge_next;
// The compare ISR wakes this early and spins to the exact tick, so ISR latency
// (e.g. a UART byte in progress) does not change the pulse width.
#define EDGE_GUARD_US 14
static uint16_t missed_ticks;
// Rest: a servo whose pulse has not changed for REST_FRAMES gets no pulse
// (no holding torque, no hum). Bit i = channel i quiet (D2, D3, D4).
#define REST_FRAMES 75
#define REST_US 3
static volatile uint8_t quiet;
static int rest_us[3];static uint8_t rest_frames[3];
static const uint8_t pin_bit[3]=PIN_BITS;
static uint8_t automatico, montaje;
static int centro[3]={1560,1470,1810},sentido[3]={1,-1,-1};
static float limit(float x,float lo,float hi){return fmaxf(lo,fminf(hi,x));}
static uint32_t esp_random(void){static uint32_t x=0x61a37bf9;x^=x<<13;x^=x>>17;x^=x<<5;return x;}
#include "../../ESP8266_RTOS/main/parpadeo_tabla.h"
static int max_apertura(void){return 60;}
#include "../../ESP8266_RTOS/main/animacion.h"
#include "command_types.h"

static void hardware_off(void){
 activo=0;TCCR2B=0;TIMSK2=0;edge_count=edge_next=0;PORTD&=~PINS;
}
// Timer2 (4 us ticks, CTC chunks of <=1 ms) wakes EDGE_GUARD_US before the next
// falling edge; the edge itself is timed on Timer1.
static void edge_schedule(void){
 int16_t d=(int16_t)(edge_end[edge_next]-TCNT1)-EDGE_GUARD_US*2;
 uint16_t n=d<16?2:(uint16_t)d/8;if(n>250)n=250;
 TCCR2B=0;TCNT2=0;OCR2A=(uint8_t)(n-1);TIFR2=_BV(OCF2A);TIMSK2=_BV(OCIE2A);TCCR2B=_BV(CS22);
}
// Timer1 fast PWM (mode 14, TOP=ICR1, no compare outputs): 20 ms frame.
ISR(TIMER1_OVF_vect){
 frames++;
 if(activo && lease && --lease==0){hardware_off();lost_link++;hardware_fault=1;fault=1;}
 if(!activo)return;
 uint8_t on=~quiet&7,bits=0,n=0;
 uint16_t w[3];
 for(uint8_t i=0;i<3;i++)if(on&(1<<i)){w[n]=pulse_us[i]*2-2; /* -1 us: spin-exit latency */edge_bit[n]=pin_bit[i];bits|=pin_bit[i];n++;}
 if(!n)return;
 uint16_t start=TCNT1;PORTD|=bits; // all edges rise together
 for(uint8_t i=0;i<n;i++)edge_end[i]=start+w[i];
 for(uint8_t i=1;i<n;i++)for(uint8_t j=i;j>0&&edge_end[j]<edge_end[j-1];j--){
  uint16_t t=edge_end[j];edge_end[j]=edge_end[j-1];edge_end[j-1]=t;uint8_t b=edge_bit[j];edge_bit[j]=edge_bit[j-1];edge_bit[j-1]=b;}
 edge_count=n;edge_next=0;edge_schedule();
}
ISR(TIMER2_COMPA_vect){
 while(edge_next<edge_count){
  uint16_t e=edge_end[edge_next];
  // Far edge: sleep again (keeps UART RX serviced between edges).
  if((int16_t)(e-TCNT1)>(EDGE_GUARD_US+10)*2){edge_schedule();return;}
  while((int16_t)(TCNT1-e)<0){}
  PORTD&=~edge_bit[edge_next++];
 }
 TCCR2B=0;TIMSK2=0;
}
ISR(USART_RX_vect){
 uint8_t status=UCSR0A,b=UDR0,next=(rx_head+1)&(RX_SIZE-1);
 if(status&(_BV(FE0)|_BV(DOR0)|_BV(UPE0)) || next==rx_tail){
  rx_errors++;hardware_off();hardware_fault=2;fault=1;return;
 }
 rx[rx_head]=b;rx_head=next;
}
static uint32_t now_frames(void){uint32_t n;ATOMIC_BLOCK(ATOMIC_RESTORESTATE){n=frames;}return n;}
static void motor_service(void);
static void raw_apply_pending(void);
static uint8_t motor_telemetry_due;
static int tx_putchar(char c,FILE*f){(void)f;while(!(UCSR0A&_BV(UDRE0))){motor_service();}UDR0=c;return 0;}
static FILE serial_out=FDEV_SETUP_STREAM(tx_putchar,NULL,_FDEV_SETUP_WRITE);
static int pulse(int i){
 float g=actual[i];
 if(i==2){g=limit(g,0,60);int n=(int)g;g=n>=60?SERVO_PARPADEO_GIRO[60]:SERVO_PARPADEO_GIRO[n]*(1-(g-n))+SERVO_PARPADEO_GIRO[n+1]*(g-n);}
 return (int)lroundf(limit(centro[i]+sentido[i]*g*10,500,2500));
}
static void rest_reset(void){quiet=0;for(int i=0;i<3;i++){rest_us[i]=-1000;rest_frames[i]=0;}}
static void output_all(void){
 int a=pulse(0),b=pulse(1),c=pulse(2),v[3]={a,b,c};
 ATOMIC_BLOCK(ATOMIC_RESTORESTATE){pulse_us[0]=a;pulse_us[1]=b;pulse_us[2]=c;}
 uint8_t q=quiet;
 for(int i=0;i<3;i++){
  if(abs(v[i]-rest_us[i])>REST_US){rest_us[i]=v[i];rest_frames[i]=0;q&=~(1<<i);}
  else if(rest_frames[i]<REST_FRAMES&&++rest_frames[i]==REST_FRAMES)q|=1<<i;
 }
 quiet=q; // read at the start of each frame: pulses are never cut short
}
static void all_off(void){
 ATOMIC_BLOCK(ATOMIC_RESTORESTATE){hardware_off();lease=0;}
 seguimiento=0;follow_rest=0;automatico=0;blink_phase=0;reset_curves();rest_reset();
}
static uint32_t processed_frames;
static void motor_service(void){uint32_t tick=now_frames();
if(tick!=processed_frames){raw_apply_pending();motor_telemetry_due=1;uint32_t delta=tick-processed_frames;processed_frames=tick;if(delta>1)missed_ticks+=(uint16_t)(delta-1);animation_tick(fminf(.05f,delta*.02f));
   // AVR double is 32-bit: keep sub-millisecond precision over long exhibitions.
   if(follow_clock>60){follow_clock-=60;follow_received-=60;for(int i=0;i<follow_stream.count;i++)follow_stream.time[i]-=60;}
   if(activo)output_all();}
}
static void power_on(void){if(activo)return;rest_reset();output_all();ATOMIC_BLOCK(ATOMIC_RESTORESTATE){lease=35;activo=1;}}
struct saved_limits {uint32_t magic;motion_limits_t limits;uint16_t crc;};
static struct saved_limits EEMEM saved;
static uint16_t checksum(const uint8_t*p,size_t n){uint16_t c=0xffff;while(n--){c^=*p++;for(int i=0;i<8;i++)c=c&1?(c>>1)^0xa001:c>>1;}return c;}
static void save_limits(void){struct saved_limits s={.magic=0x554e4f31,.limits=motion_limits};s.crc=checksum((void*)&s,sizeof(s)-2);eeprom_update_block(&s,&saved,sizeof(s));}
static void load_limits(void){struct saved_limits s;eeprom_read_block(&s,&saved,sizeof(s));if(s.magic==0x554e4f31&&s.crc==checksum((void*)&s,sizeof(s)-2)&&limits_valid(&s.limits))motion_limits=s.limits;}
static int execute(const ojo_command*c){
 switch(c->kind){
 case OJO_STATE:break;
 case OJO_ON:power_on();break;
 case OJO_OFF:all_off();break;
 case OJO_CENTER:seguimiento=follow_rest=automatico=montaje=blink_phase=0;objetivo[0]=objetivo[1]=objetivo[2]=0;break;
 case OJO_BLINK:if(!activo)return 409;blink_profile=0;start_blink();break;
 case OJO_MOVE:
  seguimiento=follow_rest=automatico=montaje=blink_phase=0;
  for(int i=0;i<3;i++)if(c->has[i])objetivo[i]=limit(c->angle[i],i==0?-55:i==1?-35:0,i==0?55:i==1?35:max_apertura());
  break;
 case OJO_FOLLOW:
  if(!activo)return 409;
  montaje=0;follow_set(c->angle[0],c->angle[1]);follow_lid=c->angle[2];follow_rest=c->rest;break;
 case OJO_LIMITS:
  if(activo||!limits_valid(&c->limits))return 409;
  {motion_limits_t old=motion_limits;motion_limits=c->limits;
   if(fabsf(actual[1]-bounded_pitch(actual[1]))>.01f||fabsf(actual[0]-bounded_yaw(actual[0],actual[1]))>.01f){motion_limits=old;return 409;}}
  save_limits();break;
 }
 return 200;
}
#include "raw_device.h"
void disable_watchdog(void) __attribute__((naked,section(".init3")));
void disable_watchdog(void){MCUSR=0;wdt_disable();}
int main(void){
 PORTD&=~PINS;DDRD|=PINS;
 TCCR1B=0;TCCR1A=_BV(WGM11);TCNT1=0;ICR1=39999;TIFR1=_BV(TOV1);TIMSK1=_BV(TOIE1);TCCR1B=_BV(WGM13)|_BV(WGM12)|_BV(CS11);
 TCCR2A=_BV(WGM21);TCCR2B=0;
 UBRR0H=0;UBRR0L=3;UCSR0A=0;UCSR0B=_BV(RXEN0)|_BV(TXEN0)|_BV(RXCIE0);UCSR0C=_BV(UCSZ01)|_BV(UCSZ00);
 stdout=&serial_out;load_limits();all_off();sei();wdt_enable(WDTO_500MS);
 static raw_decoder decoder;static raw_packet packet;
 while(1){
  wdt_reset();
  if(fault){last_fault=hardware_fault;all_off();pending_target=0;ATOMIC_BLOCK(ATOMIC_RESTORESTATE){rx_tail=rx_head;fault=0;}memset(&decoder,0,sizeof(decoder));}
  motor_service();
  uint8_t budget=96;
  while(rx_tail!=rx_head&&budget--){
   uint8_t b=rx[rx_tail];rx_tail=(rx_tail+1)&(RX_SIZE-1);
   int parsed=raw_feed(&decoder,b,&packet);
   if(parsed>0)raw_receive(&packet);else if(parsed<0)bad_frames++;
   motor_service();
  }
  if(raw_session&&motor_telemetry_due){motor_telemetry_due=0;raw_telemetry();}
 }
}
