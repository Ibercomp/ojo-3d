// Shared HTTP/UART command parsing. Pure parser is exercised on the host.
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <errno.h>
#include "motion_limits.h"
typedef enum { OJO_STATE,OJO_ON,OJO_OFF,OJO_CENTER,OJO_FOLLOW,OJO_BLINK,OJO_MOVE,OJO_LIMITS } ojo_kind;
typedef struct {ojo_kind kind;float angle[3];int has[3];int rest;motion_limits_t limits;} ojo_command;
static int ojo_path(const char*u,const char*p){size_t n=strcspn(u,"?");return n==strlen(p)&&!strncmp(u,p,n);}
static int ojo_core_path(const char*u){return ojo_path(u,"/estado")||ojo_path(u,"/encender")||ojo_path(u,"/apagar")||ojo_path(u,"/centrar")||ojo_path(u,"/seguir")||ojo_path(u,"/parpadear")||ojo_path(u,"/mover")||ojo_path(u,"/limites");}
// 1 found, 0 absent, -1 duplicate/too long; a malformed value never becomes 0.
static int ojo_param(const char*u,const char*key,char*out,size_t cap){
 const char*p=strchr(u,'?');int found=0;out[0]=0;if(!p)return 0;p++;
 while(*p){const char*end=strchr(p,'&');if(!end)end=p+strlen(p);const char*eq=memchr(p,'=',end-p);
  if(eq && (size_t)(eq-p)==strlen(key)&&!strncmp(p,key,eq-p)){
   if(found || (size_t)(end-eq-1)>=cap)return -1;
   memcpy(out,eq+1,end-eq-1);out[end-eq-1]=0;found=1;
  }p=*end?end+1:end;
 }return found;
}
static int ojo_number(const char*u,const char*key,float*out,int*present){
 char b[32],*end;int n=ojo_param(u,key,b,sizeof(b));*present=n==1;
 if(n<0){return 0;}
 if(!n){return 1;}
 if(!b[0]){return 0;}
 errno=0;float f=strtof(b,&end);if(*end||!isfinite(f)||errno==ERANGE)return 0;*out=f;return 1;
}
static int ojo_parse(const char*u,ojo_command*c){
 memset(c,0,sizeof(*c));
 if(ojo_path(u,"/estado"))c->kind=OJO_STATE;
 else if(ojo_path(u,"/encender"))c->kind=OJO_ON;
 else if(ojo_path(u,"/apagar"))c->kind=OJO_OFF;
 else if(ojo_path(u,"/centrar"))c->kind=OJO_CENTER;
 else if(ojo_path(u,"/parpadear"))c->kind=OJO_BLINK;
 else if(ojo_path(u,"/limites")){
  c->kind=OJO_LIMITS;
  for(int r=0;r<2;r++){
   char b[96],*p,*end;int16_t*v=r?c->limits.down:c->limits.up;
   if(ojo_param(u,r?"down":"up",b,sizeof(b))!=1){return 400;}p=b;
   for(int i=0;i<7;i++){if(*p<'0'||*p>'9')return 400;errno=0;long n=strtol(p,&end,10);if(errno||n<0||n>350)return 400;v[i]=n;if(i<6){if(*end!=',')return 400;p=end+1;}else if(*end)return 400;}
  }
  if(!limits_valid(&c->limits))return 400;
 }
 else if(ojo_path(u,"/seguir")||ojo_path(u,"/mover")){
  c->kind=ojo_path(u,"/seguir")?OJO_FOLLOW:OJO_MOVE;
  const char*names[]={"giro","cabeceo","parpado"};
  for(int i=0;i<3;i++)if(!ojo_number(u,names[i],&c->angle[i],&c->has[i]))return 400;
  char rest[8];int n=ojo_param(u,"reposo",rest,sizeof(rest));if(n<0 || (n&&strcmp(rest,"0")&&strcmp(rest,"1")))return 400;
  c->rest=n&&!strcmp(rest,"1");
  if(c->kind==OJO_FOLLOW && (!c->has[0]||!c->has[1]||c->angle[2]<0||c->angle[2]>(c->rest?60:32)))return 400;
 }else return 404;
 return 200;
}
// Newline-delimited @OJO <sequence> <URI>. Boot/log lines cannot be commands.
static int ojo_frame(char*line,uint32_t*seq,char**uri){
 if(strncmp(line,"@OJO ",5)){return 0;}
 char*p=line+5,*end;
 if(*p<'0'||*p>'9'){return 0;}
 errno=0;unsigned long id=strtoul(p,&end,10);
 if(errno==ERANGE||id>UINT32_MAX||*end!=' '||end[1]!='/')return 0;
 p=end+1;if(strpbrk(p," \t\r\n")||strlen(p)>240)return 0;
 *seq=(uint32_t)id;*uri=p;return 1;
}
