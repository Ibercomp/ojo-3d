// Small fixed-delay interpolation window. Never replay a backlog.
#pragma once
#include <string.h>
#define STREAM_DELAY 0.04
#define STREAM_STALE 0.10
#define STREAM_CAPACITY 8
typedef struct {double time[STREAM_CAPACITY];float pose[STREAM_CAPACITY][2];int count;} motion_stream;
static void stream_push(motion_stream*s,double now,float x,float y){
 if(s->count && now<=s->time[s->count-1]){int i=s->count-1;s->pose[i][0]=x;s->pose[i][1]=y;return;}
 if(s->count==STREAM_CAPACITY){memmove(s->time,s->time+1,sizeof(s->time[0])*(STREAM_CAPACITY-1));memmove(s->pose,s->pose+1,sizeof(s->pose[0])*(STREAM_CAPACITY-1));s->count--;}
 int i=s->count++;s->time[i]=now;s->pose[i][0]=x;s->pose[i][1]=y;
}
static void stream_reset(motion_stream*s,double now,float x,float y){s->count=0;stream_push(s,now-STREAM_DELAY,x,y);}
static void stream_sample(const motion_stream*s,double now,float*out){
 double t=now-STREAM_DELAY;
 int i=0;while(i+1<s->count && s->time[i+1]<=t)i++;
 if(i+1==s->count || t<=s->time[i]){out[0]=s->pose[i][0];out[1]=s->pose[i][1];return;}
 float u=(float)((t-s->time[i])/(s->time[i+1]-s->time[i]));
 out[0]=s->pose[i][0]+(s->pose[i+1][0]-s->pose[i][0])*u;out[1]=s->pose[i][1]+(s->pose[i+1][1]-s->pose[i][1])*u;
}
