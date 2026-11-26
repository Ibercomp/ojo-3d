// Host-only ABI for replaying the real motion/protocol code without hardware.
#define main animation_suite_main
#include "test_animacion.c"
#undef main
static int pca=1,control_source,ota_busy,montaje;
static void all_off(void){activo=0;seguimiento=0;follow_rest=0;control_source=0;reset_curves();}
static void power_on(void){all_off();activo=1;}
#include "../main/control_core.h"
#include "../main/udp_protocol.h"
static ojo_udp_session host_session;
void host_udp_open(uint32_t token,uint32_t now){host_session=(ojo_udp_session){.token=token,.last_ms=now};}
uint32_t host_udp_token(void){return host_session.token;}
int host_udp(const uint8_t*p,size_t n,uint32_t now){ojo_command c;if(!activo)host_session.token=0;return udp_decode(&host_session,p,n,now,&c)?execute_core(&c,1):400;}
void host_init(void){reset(0);automatico=0;all_off();}
void host_tick(float dt){animation_tick(dt);check_limits();}
int host_request(const char *url){ojo_command c;int r=ojo_parse(url,&c);if(r==200&&c.kind!=OJO_STATE&&c.kind!=OJO_BLINK)host_session.token=0;return r==200?execute_core(&c,1):r;}
const char *host_state(void){
 static char out[1024];
 snprintf(out,sizeof(out),"{\"firmware\":\"host-ota23\",\"activo\":%s,\"auto\":false,\"pca\":true,\"seguimiento\":%s,\"parpadeando\":%s,\"reposo\":%s,\"giro_max\":55,\"parpado_max\":60,\"parpado_seguimiento\":%.3f,\"actual\":[%.6f,%.6f,%.6f],\"velocity\":[%.6f,%.6f,%.6f],\"target\":[%.6f,%.6f,%.6f],\"centro\":[1560,1470,1810],\"sentido\":[1,-1,-1],\"us\":[1560,1470,1810]}",activo?"true":"false",seguimiento?"true":"false",blink_phase?"true":"false",follow_rest?"true":"false",follow_lid,actual[0],actual[1],actual[2],velocidad[0],velocidad[1],velocidad[2],objetivo[0],objetivo[1],objetivo[2]);
 size_t n=strlen(out)-1;
 snprintf(out+n,sizeof(out)-n,",\"limits\":{\"up\":[%d,%d,%d,%d,%d,%d,%d],\"down\":[%d,%d,%d,%d,%d,%d,%d]}}",motion_limits.up[0],motion_limits.up[1],motion_limits.up[2],motion_limits.up[3],motion_limits.up[4],motion_limits.up[5],motion_limits.up[6],motion_limits.down[0],motion_limits.down[1],motion_limits.down[2],motion_limits.down[3],motion_limits.down[4],motion_limits.down[5],motion_limits.down[6]);
 n=strlen(out)-1;
 snprintf(out+n,sizeof(out)-n,",\"gaze_speed_max\":80,\"stream_delay_ms\":40,\"stream_stale\":%s,\"stream_age_ms\":%.1f}",follow_stale?"true":"false",(follow_clock-follow_received)*1000.);
 return out;
}
