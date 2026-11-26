// Execute the real AVR ELF: binary UART, 50 Hz PWM, corruption and watchdog.
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <simavr/sim_avr.h>
#include <simavr/sim_elf.h>
#include <simavr/avr_uart.h>
#include <simavr/avr_timer.h>
#include <simavr/avr_ioport.h>
#include "../main/raw_protocol.h"
static avr_t*avr;static avr_irq_t*input;static uint16_t seq;static uint32_t session=0x12345678;
static raw_decoder decoder;static raw_packet config,telemetry,ack;static unsigned telems,bad;static double max_step;
struct pin {uint64_t rise;unsigned count;int high;double min,max;} pins[3];
static void edge(struct avr_irq_t*irq,uint32_t value,void*param){(void)irq;struct pin*p=param;int high=value&1;if(high==p->high)return;p->high=high;if(high)p->rise=avr->cycle;else{double us=(avr->cycle-p->rise)/16.;p->count++;if(p->count==1||us<p->min)p->min=us;if(us>p->max)p->max=us;}}
static void output(struct avr_irq_t*i,uint32_t value,void*p){(void)i;(void)p;raw_packet next;int n=raw_feed(&decoder,(uint8_t)value,&next);if(n<0)bad++;if(n!=1)return;
 if(next.type==RAW_CONFIG)config=next;else if(next.type==RAW_ACK)ack=next;else if(next.type==RAW_TELEMETRY){
  if(telems&&(telemetry.data[14]&1)&&(next.data[14]&1)){
   uint32_t dt=next.time_ms-telemetry.time_ms;
   for(int j=0;j<2;j++){double step=abs((int16_t)raw_u16(next.data+j*2)-(int16_t)raw_u16(telemetry.data+j*2));if(step>max_step)max_step=step;assert(step<=8.0*dt+3);}
  }
  telemetry=next;telems++;
 }
}
static void run_us(unsigned us){uint64_t end=avr->cycle+(uint64_t)us*16;while(avr->cycle<end){int s=avr_run(avr);assert(s!=cpu_Crashed&&s!=cpu_Done);}}
static uint32_t now(void){return (uint32_t)(avr->cycle/16000);}
static void transmit(raw_packet*p,int corrupt){uint8_t wire[RAW_WIRE];size_t n=raw_encode(p,wire);if(corrupt)wire[n-3]^=1;for(size_t i=0;i<n;i++){avr_raise_irq(input,wire[i]);run_us(45);}}
static uint16_t command(uint8_t type,const uint8_t*b,uint8_t length){raw_packet p={.type=type,.session=session,.seq=++seq,.time_ms=now(),.length=length};if(length)memcpy(p.data,b,length);transmit(&p,0);return p.seq;}
static void target(int yaw,int pitch,int lid,int flags){uint8_t b[7];raw_put16(b,yaw);raw_put16(b+2,pitch);raw_put16(b+4,lid);b[6]=flags;command(RAW_TARGET,b,7);}
int main(int argc,char**argv){
 assert(argc==2);elf_firmware_t fw={0};assert(!elf_read_firmware(argv[1],&fw));avr=avr_make_mcu_by_name("atmega328p");assert(avr);avr_init(avr);avr->frequency=16000000;avr_load_firmware(avr,&fw);
 input=avr_io_getirq(avr,AVR_IOCTL_UART_GETIRQ('0'),UART_IRQ_INPUT);uint32_t flags=0;avr_ioctl(avr,AVR_IOCTL_UART_SET_FLAGS('0'),&flags);avr_irq_register_notify(avr_io_getirq(avr,AVR_IOCTL_UART_GETIRQ('0'),UART_IRQ_OUTPUT),output,NULL);
 for(int i=0;i<3;i++)avr_irq_register_notify(avr_io_getirq(avr,AVR_IOCTL_IOPORT_GETIRQ('D'),2+i),edge,&pins[i]); // D2 yaw, D3 pitch, D4 lid
 run_us(200000);for(int i=0;i<3;i++)assert(!pins[i].count&&!pins[i].high);
 assert(!(avr->data[0x24]&0x0E)); // DDRB: D9-D11 stay inputs
 command(RAW_HELLO,NULL,0);run_us(30000);assert(config.session==session&&config.length==48&&config.data[0]==3);assert(!(telemetry.data[14]&1));
 uint8_t on=1,off=0;uint16_t q=command(RAW_ARM,&on,1);run_us(10000);assert(ack.seq==q&&!ack.data[0]);
 for(int i=0;i<20;i++){command(RAW_STATE,NULL,0);run_us(10000);} // STATE must not renew motion watchdog.
 for(int i=0;i<3;i++)printf("D%d fixed pulse [%.3f,%.3f] us\n",i+2,pins[i].min,pins[i].max);
 assert(pins[2].min>=1809.0&&pins[2].max<=1811.0); // lid: software edge must match order
 assert(pins[0].min>=1559&&pins[0].max<=1561&&pins[1].min>=1469&&pins[1].max<=1471);
 unsigned before=telems;uint64_t begin=avr->cycle;double max_tx=0;
 for(int i=0;i<150;i++){
  uint64_t start=avr->cycle;target((i/15)%2?2000:-2000,(i/25)%2?1000:-1000,1500,1);
  double us=(avr->cycle-start)/16.;if(us>max_tx)max_tx=us;assert(us<1500);run_us((unsigned)(20000-us));
 }
 run_us(3000);assert(!bad);assert(raw_u16(telemetry.data+16)==0);assert(raw_u16(telemetry.data+20)==0);
 printf("BENCH commands=150 simulated_s=%.3f telemetry=%u target_wire_us_max=%.3f missed_ticks=%u max_gaze_step_cdeg=%.0f\n",(avr->cycle-begin)/16000000.,telems-before,max_tx,raw_u16(telemetry.data+20),max_step);
 raw_packet p={.type=RAW_TARGET,.session=session,.seq=++seq,.time_ms=now(),.length=7};raw_put16(p.data,5500);p.data[6]=1;
 uint16_t accepted=telemetry.seq;transmit(&p,1);run_us(25000);assert(telemetry.seq==accepted&&raw_u16(telemetry.data+18)>0);
 p.seq=++seq;p.time_ms=now()-150;transmit(&p,0);run_us(25000);assert(telemetry.seq==accepted);
 p.seq=++seq;p.time_ms=now();p.session^=1;transmit(&p,0);run_us(25000);assert(telemetry.seq==accepted);
 // Last target wins within a motor tick, without playing back the burst.
 for(int i=1;i<=4;i++)target(0,0,i*100,1);run_us(40000);assert(raw_u16(telemetry.data+12)==400);
 // Telemetry/STATE activity cannot conceal a lost command stream.
 for(int i=0;i<9;i++){command(RAW_STATE,NULL,0);run_us(100000);}assert(!(telemetry.data[14]&1));assert(telemetry.data[15]==1);
 assert(!(avr->data[0x80]&0xf0)&&!(avr->data[0x2B]&0x1C));
 target(100,100,0,1);run_us(30000);assert(!(telemetry.data[14]&1));
 q=command(RAW_ARM,&on,1);run_us(10000);assert(ack.seq==q&&!ack.data[0]);
 q=command(RAW_ARM,&off,1);run_us(10000);assert(ack.seq==q&&!ack.data[0]);assert(!(avr->data[0x80]&0xf0)&&!(avr->data[0x2B]&0x1C));
 // A queued ARM from the closed session cannot undo OFF.
 command(RAW_ARM,&on,1);run_us(30000);assert(!(avr->data[0x80]&0xf0));
 session^=0x10000;command(RAW_HELLO,NULL,0);run_us(30000);assert(config.session==session);
 q=command(RAW_ARM,&on,1);run_us(10000);assert(ack.seq==q&&!ack.data[0]);
 // Rest: a still servo loses its pulse after ~1.5 s and gets it back on a new order.
 for(int i=0;i<120;i++){target(0,0,0,1);run_us(20000);}
 unsigned c0[3];for(int i=0;i<3;i++)c0[i]=pins[i].count;
 for(int i=0;i<20;i++){target(0,0,0,1);run_us(20000);}
 for(int i=0;i<3;i++)assert(pins[i].count==c0[i]);assert(!(avr->data[0x2B]&0x1C));
 // Yaw wakes alone (the firmware holds gaze while the lid moves).
 pins[0].min=1e9;pins[0].max=0;
 for(int i=1;i<=30;i++){target(i*100,0,0,1);run_us(20000);}
 assert(pins[0].count>c0[0]+25&&pins[1].count==c0[1]&&pins[2].count==c0[2]);
 printf("REST yaw pulses after wake %u [%.3f,%.3f] us\n",pins[0].count-c0[0],pins[0].min,pins[0].max);
 assert(pins[0].min>1500&&pins[0].max<2000);
 pins[2].min=1e9;pins[2].max=0;
 for(int i=1;i<=30;i++){target(3000,0,i*20,1);run_us(20000);}
 printf("REST lid pulses after wake %u [%.3f,%.3f] us\n",pins[2].count-c0[2],pins[2].min,pins[2].max);
 assert(pins[2].count>c0[2]+20&&pins[2].min>1000&&pins[2].max<2500);
 command(RAW_ARM,&off,1);run_us(10000);
 puts("OK: real binary ELF, PWM, 50 Hz stream, bad CRC, expired/foreign targets, latest-only burst, watchdog, explicit rearm and pulse rest.");
}
