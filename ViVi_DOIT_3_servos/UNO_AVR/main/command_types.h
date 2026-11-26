// Internal motor operations, independent of transport encoding.
#pragma once
#include "../../ESP8266_RTOS/main/motion_limits.h"
typedef enum {OJO_STATE,OJO_ON,OJO_OFF,OJO_CENTER,OJO_FOLLOW,OJO_BLINK,OJO_MOVE,OJO_LIMITS} ojo_kind;
typedef struct {ojo_kind kind;float angle[3];int has[3];int rest;motion_limits_t limits;} ojo_command;
