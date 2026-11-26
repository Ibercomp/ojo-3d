#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;
typedef int* i2c_cmd_handle_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM -2
#define I2C_MASTER_WRITE 0
#define I2C_MASTER_READ 1
#define I2C_MASTER_NACK 1
#define I2C_NUM_0 0
#define portTICK_RATE_MS 10
static int activo=0,pca_ultimo[16]={4096,4096};
static unsigned diag_i2c_errors;
static uint8_t registers[256],reg,*destination;
static int step,reads,fail_reg=-1,allocate=1;
static int pulse(int i){return i?1398:1990;}
static unsigned xTaskGetTickCount(void){return 100;}
static i2c_cmd_handle_t i2c_cmd_link_create(void){step=0;return allocate?&step:NULL;}
static void i2c_master_start(i2c_cmd_handle_t c){assert(c==&step);assert(step==0||step==3);step++;}
static void i2c_master_write_byte(i2c_cmd_handle_t c,uint8_t b,int ack){
 assert(c==&step&&ack);
 if(step==1){assert(b==0x80);step=2;}
 else if(step==2){reg=b;step=3;}
 else{assert(step==4&&b==0x81);step=5;}
}
static void i2c_master_read_byte(i2c_cmd_handle_t c,uint8_t*p,int ack){assert(c==&step&&step==5&&ack==I2C_MASTER_NACK);destination=p;step=6;}
static void i2c_master_stop(i2c_cmd_handle_t c){assert(c==&step&&step==6);step=7;}
static esp_err_t i2c_master_cmd_begin(int bus,i2c_cmd_handle_t c,int timeout){
 assert(bus==0&&c==&step&&step==7&&timeout==10);reads++;
 if(reg==fail_reg)return ESP_FAIL;
 *destination=registers[reg];return ESP_OK;
}
static void i2c_cmd_link_delete(i2c_cmd_handle_t c){assert(c==&step&&step==7);}
#include "../main/pca_diagnostic.h"
int main(void){
 char result[640];
 registers[0]=1; // AI disabled, as after a reset: each register must be addressed.
 registers[1]=4;registers[0xfe]=30;
 for(int i=6;i<14;i++)registers[i]=(uint8_t)(i-5);
 assert(pca_diagnostic(result,sizeof(result))==200);
 assert(reads==15&&!activo&&!diag_i2c_errors);
 assert(strstr(result,"\"mode1\":1")&&strstr(result,"\"prescale\":30"));
 assert(strstr(result,"\"led\":[[1,2,3,4],[5,6,7,8]]"));
 assert(pca_ultimo[0]==4096&&pca_ultimo[1]==4096);
 fail_reg=0xfe;reads=0;
 assert(pca_diagnostic(result,sizeof(result))==503);
 assert(reads==3&&diag_i2c_errors==1&&strstr(result,"\"reg\":254"));
 fail_reg=-1;allocate=0;
 assert(pca_diagnostic(result,sizeof(result))==503);
 assert(diag_i2c_errors==1); // Allocation failure is not a bus failure.
 puts("OK: single-byte readback survives lost AI; bus/allocation faults reported; no PWM writes.");
}
