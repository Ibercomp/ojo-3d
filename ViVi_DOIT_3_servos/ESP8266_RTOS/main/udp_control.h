#pragma once
static void udp_control(void*arg){
 (void)arg;int fd=socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);
 struct sockaddr_in local={.sin_family=AF_INET,.sin_port=htons(4210),.sin_addr.s_addr=htonl(INADDR_ANY)};
 if(fd<0||bind(fd,(struct sockaddr*)&local,sizeof(local))<0){if(fd>=0)close(fd);vTaskDelete(NULL);return;}
 struct timeval timeout={.tv_sec=0,.tv_usec=20000};setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
 while(1){
  uint8_t packet[64],reply[36]={0};struct sockaddr_in peer;socklen_t len=sizeof(peer);
  int n=recvfrom(fd,packet,sizeof(packet),0,(struct sockaddr*)&peer,&len);if(n<0){vTaskDelay(1);continue;}
  int accepted=0;ojo_command c;
  xSemaphoreTake(lock,portMAX_DELAY);
  uint32_t now=xTaskGetTickCount()*portTICK_RATE_MS;
  if(!activo||ota_busy)udp_session.token=0;
  if(udp_decode(&udp_session,packet,n,now,&c)&&execute_core(&c,1)==200){
   accepted=1;memcpy(reply,"OS19",4);udp_put32(reply+4,udp_session.token);udp_put32(reply+8,udp_session.seq);udp_put32(reply+12,now);
   for(int i=0;i<3;i++)udp_put16(reply+16+i*2,(int16_t)lroundf(actual[i]*100));
   udp_put16(reply+22,(uint16_t)lroundf(follow_lid*100));
   reply[24]=(activo?1:0)|(seguimiento?2:0)|(blink_phase?4:0)|(follow_rest?8:0)|(pca?16:0);
   udp_put16(reply+28,diag_wifi_drops);udp_put16(reply+30,diag_i2c_errors);udp_put16(reply+32,diag_drive_gap_ms);
  }
  xSemaphoreGive(lock);
  if(accepted)sendto(fd,reply,sizeof(reply),0,(struct sockaddr*)&peer,len);
 }
}
