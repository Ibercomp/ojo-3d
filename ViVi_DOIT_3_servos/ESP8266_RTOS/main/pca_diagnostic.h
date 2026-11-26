// Register readback only: does not reconfigure PWM or enable outputs.
#pragma once
#include <stdbool.h>
static esp_err_t pca_read_byte(uint8_t reg,uint8_t*out){
 i2c_cmd_handle_t c=i2c_cmd_link_create();if(!c)return ESP_ERR_NO_MEM;
 i2c_master_start(c);
 i2c_master_write_byte(c,0x40<<1|I2C_MASTER_WRITE,true);
 i2c_master_write_byte(c,reg,true);
 i2c_master_start(c);
 i2c_master_write_byte(c,0x40<<1|I2C_MASTER_READ,true);
 i2c_master_read_byte(c,out,I2C_MASTER_NACK);
 i2c_master_stop(c);
 esp_err_t e=i2c_master_cmd_begin(I2C_NUM_0,c,100/portTICK_RATE_MS);
 i2c_cmd_link_delete(c);if(e!=ESP_OK)diag_i2c_errors++;return e;
}
// Read every byte separately: a lost MODE1.AI must not corrupt this readback.
// Caller holds the motor mutex, so register values and cached ticks agree in time.
static int pca_diagnostic(char*out,size_t cap){
 const uint8_t regs[]={0,1,0xfe,6,7,8,9,10,11,12,13,0xfa,0xfb,0xfc,0xfd};
 uint8_t b[sizeof(regs)];
 for(size_t i=0;i<sizeof(regs);i++){
  esp_err_t e=pca_read_byte(regs[i],&b[i]);
  if(e!=ESP_OK){snprintf(out,cap,"{\"error\":\"pca_read\",\"reg\":%u,\"code\":%d}",regs[i],(int)e);return 503;}
 }
 snprintf(out,cap,"{\"diagnostic\":\"pca_registers_v1\",\"activo\":%s,\"uptime_ms\":%u,\"mode1\":%u,\"mode2\":%u,\"prescale\":%u,\"led\":[[%u,%u,%u,%u],[%u,%u,%u,%u]],\"all_led\":[%u,%u,%u,%u],\"cached_ticks\":[%d,%d],\"command_us\":[%d,%d],\"i2c_errors\":%u}",
  activo?"true":"false",(unsigned)(xTaskGetTickCount()*portTICK_RATE_MS),
  b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[8],b[9],b[10],b[11],b[12],b[13],b[14],
  pca_ultimo[0],pca_ultimo[1],pulse(0),pulse(1),diag_i2c_errors);
 return 200;
}
