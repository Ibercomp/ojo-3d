#define main animation_suite_main
#include "test_animacion.c"
#undef main
static int pca=1,control_source,ota_busy,montaje;
static void all_off(void){activo=0;seguimiento=0;follow_rest=0;control_source=0;reset_curves();}
static void power_on(void){all_off();activo=1;}
#include "../main/control_core.h"
static int request(const char*url,int source){ojo_command c;int r=ojo_parse(url,&c);return r==200?execute_core(&c,source):r;}
int main(void){
 ojo_command c;assert(ojo_core_path("/estado"));assert(!ojo_core_path("/estado_bad"));
 const char*invalid[]={"/seguir?giro=nan&cabeceo=0","/seguir?giro=0","/seguir?giro=&cabeceo=0","/seguir?giro=1oops&cabeceo=0","/seguir?giro=1&giro=2&cabeceo=0","/seguir?giro=1&cabeceo=0&parpado=60","/seguir?giro=1&cabeceo=0&reposo=2"};
 for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);i++)assert(ojo_parse(invalid[i],&c)==400);
 assert(ojo_parse("/seguir_extra?giro=0&cabeceo=0",&c)==404);
 assert(ojo_parse("/seguir?giro=-3.5&cabeceo=2&parpado=60&reposo=1",&c)==200&&c.rest&&c.angle[2]==60);
 char frame[]="@OJO 42 /estado";uint32_t seq;char*uri;assert(ojo_frame(frame,&seq,&uri)&&seq==42&&!strcmp(uri,"/estado"));
 char bad[]="@OJO 4294967296 /estado";assert(!ojo_frame(bad,&seq,&uri));
 char boot[]="boot log /encender";assert(!ojo_frame(boot,&seq,&uri));
 reset(0);automatico=0;all_off();assert(request("/seguir?giro=0&cabeceo=0",2)==409);
 assert(request("/encender",2)==200&&activo&&control_source==2);
 control_wifi_lost();assert(activo); // UART must work even with Wi-Fi disconnected.
 for(int k=0;k<400;k++){assert(request("/seguir?giro=0&cabeceo=0&parpado=60&reposo=1",2)==200);animation_tick(.02f);check_limits();assert(!blink_phase);}
 assert(actual[2]>59.99f&&follow_rest);
 for(int k=0;k<100;k++){request("/seguir?giro=-27&cabeceo=0&parpado=0&reposo=1",2);animation_tick(.02f);check_limits();}
 assert(fabsf(actual[0]+27)<.02f&&actual[2]<.01f);
 for(int k=0;k<100;k++){animation_tick(.02f);}
 assert(!seguimiento&&actual[2]<.01f);
 ota_busy=1;assert(request("/encender",2)==409);ota_busy=0;
 request("/encender",1);control_wifi_lost();assert(!activo);
 puts("OK: protocolo comun, UART, reposo, rechazo atomico, watchdog y propiedad del enlace.");
}
