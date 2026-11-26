#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_http_server.h"
#include "lwip/sockets.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "driver/pwm.h"
#ifdef CONFIG_ESP8266_NMI_WDT
#error "NMI watchdog is incompatible with SDK PWM: disable ESP8266_NMI_WDT, keep ESP_TASK_WDT"
#endif
#include "driver/uart.h"
#include "spi_flash.h"
#include "wifi_privada.h"
#include "parpadeo_tabla.h"
#define httpd_resp_sendstr(r,s) httpd_resp_send((r),(s),strlen(s))
#define HTTPD_403_FORBIDDEN "403 Forbidden"
#define HTTPD_400_BAD_REQUEST "400 Bad Request"
#define HTTPD_500_INTERNAL_SERVER_ERROR "500 Internal Server Error"
static esp_err_t httpd_resp_send_err(httpd_req_t *r,const char *status,const char *message){httpd_resp_set_status(r,status);return httpd_resp_send(r,message,strlen(message));}

extern const unsigned char pagina_start[] asm("_binary_pagina_html_start");
extern const unsigned char pagina_end[] asm("_binary_pagina_html_end");
static const char *TAG="ojo";
static SemaphoreHandle_t lock;
static int pca, activo, automatico, montaje=1;
static int control_source,ota_busy; // 1 Wi-Fi, 2 UART
static int canales[3]={0,1,17}, sentido[3]={1,1,1}, centro[3]={1500,1500,1135};
static int pca_ultimo[16];
static unsigned diag_wifi_drops,diag_i2c_errors,diag_drive_gap_ms;
static nvs_handle nh;
static uint32_t direct_duty[2]={0,0};
static const uint32_t direct_pin[2]={12,14};
static float limit(float x,float a,float b){return x<a?a:x>b?b:x;}
static int max_apertura(void);
#include "animacion.h"
static esp_err_t write_reg(uint8_t reg,const uint8_t *data,size_t n){
 i2c_cmd_handle_t c=i2c_cmd_link_create();i2c_master_start(c);i2c_master_write_byte(c,0x40<<1|I2C_MASTER_WRITE,true);i2c_master_write_byte(c,reg,true);if(n)i2c_master_write(c,(uint8_t*)data,n,true);i2c_master_stop(c);esp_err_t e=i2c_master_cmd_begin(I2C_NUM_0,c,100/portTICK_RATE_MS);i2c_cmd_link_delete(c);if(e!=ESP_OK)diag_i2c_errors++;return e;
}
static void pca_write(int c,int us){uint8_t b[4]={0};int ticks;if(us<=0){b[3]=0x10;ticks=4096;}else{ticks=(us*4096+10000)/20000;b[2]=ticks&255;b[3]=ticks>>8;}if(pca_ultimo[c]!=ticks && write_reg(6+4*c,b,4)==ESP_OK)pca_ultimo[c]=ticks;}
static int max_apertura(void){
 if(centro[2]<500||centro[2]>2500)return 0;
 int max=0; for(int i=1;i<=PARPADO_MAX_DEG;i++){float us=centro[2]+sentido[2]*SERVO_PARPADEO_GIRO[i]*10.0f;if(us<500||us>2500)break;max=i;}return max;
}
static int pulse(int i){float g=actual[i];if(i==2){g=limit(g,0,60);int n=(int)g;g=n>=60?SERVO_PARPADEO_GIRO[60]:SERVO_PARPADEO_GIRO[n]*(1-(g-n))+SERVO_PARPADEO_GIRO[n+1]*(g-n);}return (int)lroundf(limit(centro[i]+sentido[i]*g*10,500,2500));}
#include "servo_output.h"
#include "udp_protocol.h"
static ojo_udp_session udp_session;
static void save_config(void){nvs_set_blob(nh,"canales",canales,sizeof(canales));nvs_set_blob(nh,"centro",centro,sizeof(centro));nvs_set_blob(nh,"sentido",sentido,sizeof(sentido));nvs_set_u32(nh,"cal_ver",3);nvs_commit(nh);}
static void load_config(void){
 size_t n=sizeof(canales); nvs_get_blob(nh,"canales",canales,&n);
 int old_center[3],old_sign[3]; n=sizeof(old_center); esp_err_t ec=nvs_get_blob(nh,"centro",old_center,&n);
 n=sizeof(old_sign); esp_err_t es=nvs_get_blob(nh,"sentido",old_sign,&n);
 uint32_t ver=0; nvs_get_u32(nh,"cal_ver",&ver);
 if(ec==ESP_OK && es==ESP_OK){
  memcpy(centro,old_center,sizeof(centro)); memcpy(sentido,old_sign,sizeof(sentido));
  if(ver<3){centro[2]=(int)lroundf(centro[2]+sentido[2]*SERVO_PARPADEO_GIRO[PARPADO_MAX_DEG]*10.0f);sentido[2]=-sentido[2];}
 } else {
  // Calibración en el formato del firmware Arduino anterior: struct de 16 bytes al final de la flash de 4 MB.
  struct { uint32_t magic; int8_t channel[3]; int8_t sign[3]; int16_t mid[3]; } old;
  if(spi_flash_read(0x3fb000,&old,sizeof(old))==ESP_OK && (old.magic==0x4f4a4f02 || old.magic==0x4f4a4f03)){
   bool valid=true; for(int i=0;i<3;i++)if(old.channel[i]<0||old.channel[i]>=18||(old.sign[i]!=1&&old.sign[i]!=-1)||old.mid[i]<700||old.mid[i]>3000)valid=false;
   if(valid){for(int i=0;i<3;i++){canales[i]=old.channel[i];sentido[i]=old.sign[i];centro[i]=old.mid[i];}
    if(old.magic==0x4f4a4f02){centro[2]=(int)lroundf(centro[2]+sentido[2]*SERVO_PARPADEO_GIRO[PARPADO_MAX_DEG]*10.0f);sentido[2]=-sentido[2];}
    ESP_LOGI(TAG,"Calibracion anterior importada de EEPROM");
   }
  }
 }
 size_t ln=sizeof(motion_limits);motion_limits_t stored;
 if(nvs_get_blob(nh,"limits_v1",&stored,&ln)==ESP_OK && ln==sizeof(stored) && limits_valid(&stored))motion_limits=stored;
 save_config();
}
static void query(httpd_req_t*r,const char*k,char *v,size_t n){char b[256];v[0]=0;if(httpd_req_get_url_query_str(r,b,sizeof(b))==ESP_OK)httpd_query_key_value(b,k,v,n);}
static int axis(const char*s){return !strcmp(s,"giro")?0:!strcmp(s,"cabeceo")?1:!strcmp(s,"parpado")?2:-1;}
static void format_state(char *b,size_t size){char lim[160];
 snprintf(lim,sizeof(lim),"{\"up\":[%d,%d,%d,%d,%d,%d,%d],\"down\":[%d,%d,%d,%d,%d,%d,%d]}",motion_limits.up[0],motion_limits.up[1],motion_limits.up[2],motion_limits.up[3],motion_limits.up[4],motion_limits.up[5],motion_limits.up[6],motion_limits.down[0],motion_limits.down[1],motion_limits.down[2],motion_limits.down[3],motion_limits.down[4],motion_limits.down[5],motion_limits.down[6]);
 char angle[3][24];for(int i=0;i<3;i++){int v=(int)lroundf(actual[i]*1000.0f),m=abs(v);snprintf(angle[i],sizeof(angle[i]),"%s%d.%03d",v<0?"-":"",m/1000,m%1000);}snprintf(b,size,"{\"firmware\":\"rtos-ota-24-diag\",\"limits\":%s,\"udp_port\":4210,\"udp_session\":%u,\"reposo\":%s,\"uart\":true,\"giro_max\":55,\"gaze_speed_max\":80,\"stream_delay_ms\":40,\"parpado_seguimiento\":%d,\"seguimiento\":%s,\"parpadeando\":%s,\"actual\":[%s,%s,%s],\"patron\":\"%s\",\"parpado_max\":%d,\"pca\":%s,\"activo\":%s,\"auto\":%s,\"giro\":%d,\"cabeceo\":%d,\"parpado\":%d,\"canal\":[%d,%d,%d],\"buscando\":-1,\"candidato\":0,\"sentido\":[%d,%d,%d],\"centro\":[%d,%d,%d],\"us\":[%d,%d,%d],\"montaje\":%s,\"diag\":{\"uptime_ms\":%u,\"reset\":%d,\"wifi_drops\":%u,\"i2c_errors\":%u,\"drive_gap_ms\":%u}}",lim,(unsigned)udp_session.token,follow_rest?"true":"false",(int)lroundf(follow_lid),seguimiento?"true":"false",blink_phase?"true":"false",angle[0],angle[1],angle[2],patron_nombre(demo_patron),max_apertura(),pca?"true":"false",activo?"true":"false",automatico?"true":"false",(int)lroundf(objetivo[0]),(int)lroundf(objetivo[1]),(int)lroundf(objetivo[2]),canales[0],canales[1],canales[2],sentido[0],sentido[1],sentido[2],centro[0],centro[1],centro[2],pulse(0),pulse(1),pulse(2),montaje?"true":"false",(unsigned)(xTaskGetTickCount()*portTICK_RATE_MS),(int)esp_reset_reason(),diag_wifi_drops,diag_i2c_errors,diag_drive_gap_ms);}
static esp_err_t root(httpd_req_t*r){httpd_resp_set_type(r,"text/html; charset=utf-8");return httpd_resp_send(r,(const char*)pagina_start,pagina_end-pagina_start-1);}
#include "control_core.h"
#include "pca_diagnostic.h"
static int run_core(const char*url,int source,char*response,size_t size){
 if(ojo_path(url,"/pca")){xSemaphoreTake(lock,portMAX_DELAY);int result=pca_diagnostic(response,size);xSemaphoreGive(lock);return result;}
 ojo_command cmd;int code=ojo_parse(url,&cmd);
 xSemaphoreTake(lock,portMAX_DELAY);
 if(code==200){
  if(cmd.kind!=OJO_STATE && cmd.kind!=OJO_BLINK)udp_session.token=0;
  motion_limits_t old=motion_limits;
  code=execute_core(&cmd,source);
  if(code==200&&cmd.kind==OJO_LIMITS){
   if(nvs_set_blob(nh,"limits_v1",&motion_limits,sizeof(motion_limits))!=ESP_OK||nvs_commit(nh)!=ESP_OK){motion_limits=old;code=503;}
  }
 }
 if(code==200)format_state(response,size);
 else snprintf(response,size,"{\"error\":\"Orden no valida, salidas apagadas u OTA en curso\"}");
 xSemaphoreGive(lock);return code;
}
#include "udp_control.h"
static esp_err_t control(httpd_req_t*r){
 if(ojo_path(r->uri,"/pca")){char body[640];int code=run_core(r->uri,0,body,sizeof(body));httpd_resp_set_type(r,"application/json");if(code!=200)httpd_resp_set_status(r,"503 Service Unavailable");return httpd_resp_sendstr(r,body);}
 if(ojo_path(r->uri,"/udp")){
  char response[1024];xSemaphoreTake(lock,portMAX_DELAY);
  if(ota_busy||!activo){xSemaphoreGive(lock);return httpd_resp_send_err(r,"409 Conflict","Enciende el ojo antes de abrir UDP");}
  udp_session=(ojo_udp_session){.token=esp_random()|1,.last_ms=xTaskGetTickCount()*portTICK_RATE_MS};
  format_state(response,sizeof(response));xSemaphoreGive(lock);
  httpd_resp_set_type(r,"application/json");return httpd_resp_sendstr(r,response);
 }

 if(ojo_core_path(r->uri)){
  char response[1024];int code=run_core(r->uri,1,response,sizeof(response));
  if(code!=200)httpd_resp_set_status(r,code==400?"400 Bad Request":code==409?"409 Conflict":"503 Service Unavailable");
  httpd_resp_set_type(r,"application/json");return httpd_resp_sendstr(r,response);
 }
 char v[32];xSemaphoreTake(lock,portMAX_DELAY);const char*u=r->uri;
 if(ota_busy){xSemaphoreGive(lock);return httpd_resp_send_err(r,"409 Conflict","OTA en curso");}
 control_source=1;udp_session.token=0;
 if(!strncmp(u,"/montaje",8)){seguimiento=0;follow_rest=0;objetivo[0]=objetivo[1]=objetivo[2]=0;blink_phase=0;automatico=0;montaje=1;}
 else if(!strncmp(u,"/auto",5)){seguimiento=0;query(r,"on",v,sizeof(v));automatico=atoi(v)==1;if(automatico){blink_phase=0;demo_phase=0;demo_ticks=0;demo_patron=0;natural_blink_ticks=0;objetivo[2]=0;hold_gaze();}montaje=0;}else if(!strncmp(u,"/patron",7)){seguimiento=0;query(r,"nombre",v,sizeof(v));int id=patron_id(v);if(id<0){xSemaphoreGive(lock);return httpd_resp_send_err(r,HTTPD_400_BAD_REQUEST,"Patron desconocido");}if(id>=0){natural_blink_ticks=0;demo_patron=id;demo_phase=0;demo_ticks=0;blink_phase=0;automatico=1;montaje=0;objetivo[2]=0;hold_gaze();}}else if(!strncmp(u,"/ajuste",7)){query(r,"eje",v,sizeof(v));int i=axis(v);if(i>=0){query(r,"centro",v,sizeof(v));if(v[0])centro[i]=(int)limit(atoi(v),700,2300);query(r,"sentido",v,sizeof(v));if(v[0])sentido[i]=atoi(v)<0?-1:1;query(r,"canal",v,sizeof(v));if(v[0]&&!activo){int c=atoi(v);if(c>=0&&c<18)canales[i]=c;}save_config();}}
 char response[1024];format_state(response,sizeof(response));xSemaphoreGive(lock);
 // Socket backpressure must never block the 50 Hz motor task.
 httpd_resp_set_type(r,"application/json");return httpd_resp_sendstr(r,response);}

static void serial_control(void*arg){
 (void)arg;char line[288],body[1024],reply[1100];size_t used=0;int overflow=0;
 while(1){uint8_t byte;if(uart_read_bytes(UART_NUM_0,&byte,1,50/portTICK_RATE_MS)<=0)continue;
  if(byte=='\r')continue;
  if(byte!='\n'){if(used+1<sizeof(line)&&!overflow)line[used++]=(char)byte;else overflow=1;continue;}
  line[used]=0;
  if(!overflow){uint32_t seq;char*uri;
   if(ojo_frame(line,&seq,&uri)){
    int code=run_core(uri,2,body,sizeof(body));
    int n=snprintf(reply,sizeof(reply),"@OJO %lu %d %s\n",(unsigned long)seq,code,body);
    uart_write_bytes(UART_NUM_0,reply,n);
   }
  }
  used=0;overflow=0;
 }
}
static esp_err_t ota(httpd_req_t*r){char token[96];if(httpd_req_get_hdr_value_str(r,"X-Ojo-OTA",token,sizeof(token))!=ESP_OK||strcmp(token,OTA_TOKEN)){httpd_resp_send_err(r,HTTPD_403_FORBIDDEN,"Acceso denegado");return ESP_FAIL;}const esp_partition_t*part=esp_ota_get_next_update_partition(NULL);if(!part||r->content_len<=0||r->content_len>part->size){httpd_resp_send_err(r,HTTPD_400_BAD_REQUEST,"Tamano invalido");return ESP_FAIL;}xSemaphoreTake(lock,portMAX_DELAY);ota_busy=1;udp_session.token=0;all_off();xSemaphoreGive(lock);esp_ota_handle_t h;esp_err_t e=esp_ota_begin(part,r->content_len,&h);if(e!=ESP_OK){httpd_resp_send_err(r,HTTPD_500_INTERNAL_SERVER_ERROR,"OTA inicio fallido");ota_busy=0;return ESP_FAIL;}int remaining=r->content_len;char b[1024];while(remaining>0){int n=httpd_req_recv(r,b,remaining>(int)sizeof(b)?sizeof(b):remaining);if(n<=0){esp_ota_end(h);ota_busy=0;return ESP_FAIL;}if(esp_ota_write(h,b,n)!=ESP_OK){esp_ota_end(h);ota_busy=0;return ESP_FAIL;}remaining-=n;}if(esp_ota_end(h)!=ESP_OK||esp_ota_set_boot_partition(part)!=ESP_OK){httpd_resp_send_err(r,HTTPD_500_INTERNAL_SERVER_ERROR,"Imagen invalida");ota_busy=0;return ESP_FAIL;}httpd_resp_sendstr(r,"Actualizacion validada; reiniciando");vTaskDelay(200/portTICK_RATE_MS);esp_restart();return ESP_OK;}
static void event(void*a,esp_event_base_t b,int32_t id,void*d){if(b==WIFI_EVENT&&id==WIFI_EVENT_STA_START)esp_wifi_connect();else if(b==WIFI_EVENT&&id==WIFI_EVENT_STA_DISCONNECTED){xSemaphoreTake(lock,portMAX_DELAY);diag_wifi_drops++;udp_session.token=0;control_wifi_lost();xSemaphoreGive(lock);esp_wifi_connect();}else if(b==IP_EVENT&&id==IP_EVENT_STA_GOT_IP){ip_event_got_ip_t *ip=d;ESP_LOGI(TAG,"IP: %s",ip4addr_ntoa(&ip->ip_info.ip));}}
static void drive(void*a){
 TickType_t ultima=xTaskGetTickCount(),anterior=ultima;
 while(1){
  vTaskDelayUntil(&ultima,20/portTICK_RATE_MS);
  TickType_t ahora=xTaskGetTickCount();unsigned gap=(ahora-anterior)*portTICK_RATE_MS;float dt=limit((ahora-anterior)*portTICK_RATE_MS/1000.0f,0.001f,0.05f);anterior=ahora;
  xSemaphoreTake(lock,portMAX_DELAY);
  if(activo && gap>diag_drive_gap_ms)diag_drive_gap_ms=gap;
  animation_tick(dt);output_all();xSemaphoreGive(lock);
 }
}
static esp_err_t socket_open(httpd_handle_t server,int fd){
 (void)server;int one=1;
 return setsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&one,sizeof(one))==0?ESP_OK:ESP_FAIL;
}
void app_main(void){lock=xSemaphoreCreateMutex();gpio_set_level(GPIO_NUM_13,1);gpio_set_direction(GPIO_NUM_13,GPIO_MODE_OUTPUT);gpio_set_level(GPIO_NUM_12,0);gpio_set_level(GPIO_NUM_14,0);gpio_set_direction(GPIO_NUM_12,GPIO_MODE_OUTPUT);gpio_set_direction(GPIO_NUM_14,GPIO_MODE_OUTPUT);esp_err_t nv=nvs_flash_init();if(nv==ESP_ERR_NVS_NO_FREE_PAGES||nv==ESP_ERR_NVS_NEW_VERSION_FOUND){ESP_ERROR_CHECK(nvs_flash_erase());nv=nvs_flash_init();}ESP_ERROR_CHECK(nv);ESP_ERROR_CHECK(nvs_open("ojo",NVS_READWRITE,&nh));load_config();i2c_config_t c={.mode=I2C_MODE_MASTER,.sda_io_num=4,.sda_pullup_en=1,.scl_io_num=5,.scl_pullup_en=1,.clk_stretch_tick=300};ESP_ERROR_CHECK(i2c_driver_install(I2C_NUM_0,c.mode));ESP_ERROR_CHECK(i2c_param_config(I2C_NUM_0,&c));uint8_t v=0x10;pca=write_reg(0,&v,1)==ESP_OK;if(pca){v=121;write_reg(0xfe,&v,1);v=0x20;write_reg(0,&v,1);vTaskDelay(5/portTICK_RATE_MS);v=0xa0;write_reg(0,&v,1);}ESP_ERROR_CHECK(pwm_init(20000,direct_duty,2,direct_pin));all_off();tcpip_adapter_init();ESP_ERROR_CHECK(esp_event_loop_create_default());wifi_init_config_t w=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&w));ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,event,NULL));ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,event,NULL));wifi_config_t cfg={.sta={.ssid=WIFI_SSID,.password=WIFI_PASSWORD}};ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));ESP_ERROR_CHECK(esp_wifi_set_config(ESP_IF_WIFI_STA,&cfg));ESP_ERROR_CHECK(esp_wifi_start());ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));httpd_config_t h=HTTPD_DEFAULT_CONFIG();h.open_fn=socket_open;h.max_uri_handlers=16;h.stack_size=8192;httpd_handle_t srv=NULL;ESP_ERROR_CHECK(httpd_start(&srv,&h));const char *routes[]={"/estado","/encender","/apagar","/mover","/centrar","/montaje","/auto","/ajuste","/parpadear","/patron","/seguir","/udp","/limites","/pca"};httpd_uri_t uri={.method=HTTP_GET,.handler=control};httpd_uri_t home={.uri="/",.method=HTTP_GET,.handler=root};httpd_register_uri_handler(srv,&home);for(size_t i=0;i<sizeof(routes)/sizeof(routes[0]);i++){uri.uri=routes[i];httpd_register_uri_handler(srv,&uri);}httpd_uri_t update={.uri="/ota",.method=HTTP_POST,.handler=ota};httpd_register_uri_handler(srv,&update);xTaskCreate(drive,"drive",3072,NULL,5,NULL);xTaskCreate(udp_control,"ojo_udp",2048,NULL,4,NULL);
 // Runtime logging shares UART0; keep control frames intact. Boot output is
 // ignored by the host until the @OJO response prefix and sequence match.
 esp_log_level_set("*",ESP_LOG_NONE);
 uart_config_t serial_cfg={.baud_rate=230400,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE};
 ESP_ERROR_CHECK(uart_param_config(UART_NUM_0,&serial_cfg));
 ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0,1024,0,0,NULL,0));
 xTaskCreate(serial_control,"ojo_uart",4096,NULL,4,NULL);
}
