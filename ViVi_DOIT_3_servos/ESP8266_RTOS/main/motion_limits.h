#pragma once
#include <stdint.h>
#include <math.h>
typedef struct {int16_t up[7],down[7];} motion_limits_t;
static motion_limits_t motion_limits={{0,150,250,250,250,150,0},{0,150,250,250,250,150,0}};
static const float limits_yaw[7]={-55,-45,-30,0,30,45,55};
static int limits_valid(const motion_limits_t*l){
 for(int r=0;r<2;r++){const int16_t*v=r?l->down:l->up;
  if(v[3]<100)return 0;
  for(int i=0;i<7;i++)if(v[i]<0||v[i]>350)return 0;
  for(int i=0;i<3;i++)if(v[i]>v[i+1]||v[6-i]>v[5-i])return 0;
  for(int i=0;i<5;i++)if((v[i+1]-v[i])/(limits_yaw[i+1]-limits_yaw[i])+0.0001f<(v[i+2]-v[i+1])/(limits_yaw[i+2]-limits_yaw[i+1]))return 0;
 }return 1;
}
static float pitch_bound(float yaw,int upper){
 const int16_t*v=upper?motion_limits.up:motion_limits.down;int i=0;while(i<5&&yaw>limits_yaw[i+1])i++;
 float t=fmaxf(0,fminf(1,(yaw-limits_yaw[i])/(limits_yaw[i+1]-limits_yaw[i])));
 return (v[i]+(v[i+1]-v[i])*t)*0.1f;
}
static float yaw_bound(float pitch,int positive){
 const int16_t*v=pitch>=0?motion_limits.up:motion_limits.down;float y=fabsf(pitch)*10,lo=0,hi=0;
 for(int i=0;i<6;i++){
  float a=v[i],b=v[i+1];
  if(a>=y){lo=fminf(lo,limits_yaw[i]);hi=fmaxf(hi,limits_yaw[i]);}
  if(b>=y){lo=fminf(lo,limits_yaw[i+1]);hi=fmaxf(hi,limits_yaw[i+1]);}
  if((a<y&&b>=y)||(a>=y&&b<y)){float x=limits_yaw[i]+(limits_yaw[i+1]-limits_yaw[i])*(y-a)/(b-a);lo=fminf(lo,x);hi=fmaxf(hi,x);}
 }return positive?hi:lo;
}
static float bounded_pitch(float p){return fmaxf(-motion_limits.down[3]*0.1f,fminf(motion_limits.up[3]*0.1f,p));}
static float bounded_yaw(float yaw,float pitch){return fmaxf(yaw_bound(pitch,0),fminf(yaw_bound(pitch,1),yaw));}
static float transition_yaw(float yaw,float from_pitch,float to_pitch){
 float lo=fmaxf(yaw_bound(from_pitch,0),yaw_bound(to_pitch,0)),hi=fminf(yaw_bound(from_pitch,1),yaw_bound(to_pitch,1));
 return fmaxf(lo,fminf(hi,yaw));
}
