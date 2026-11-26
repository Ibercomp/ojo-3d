// Ojo animatrónico Ø150 — control de 3 servos (yaw, pitch, parpadeo) en un ESP32.
// Modo automático: mirada con sacadas aleatorias, parpadeo natural y párpado que sigue la mirada vertical.
// Modo manual: página web en http://192.168.4.1 (WiFi "OjoAnimatronico") o comandos por la consola serie.
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include "config.h"
#include "parpadeo_tabla.h"
#include "pagina.h"

// ------------------------------------------------------------------ servos
struct Eje {
  Servo servo;
  const CalServo* cal;
  float actual = 0, objetivo = 0;   // grados del movimiento del ojo
  float vel = 250;                  // °/s máximos
  bool crudo = false;               // calibración: se manda us_crudo tal cual
  float us_crudo = 1500;
};
Eje yaw, pitch, parpado;

static float limitar(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

// apertura del párpado (0 cerrado … PARPADO_MAX_DEG) → giro del servo según el cuadrilátero real (tabla)
static float giroParpadeo(float apertura) {
  apertura = limitar(apertura, 0, PARPADO_MAX_DEG);
  int i = (int)apertura;
  if (i >= PARPADO_MAX_DEG) return SERVO_PARPADEO_GIRO[PARPADO_MAX_DEG];
  float f = apertura - i;
  return SERVO_PARPADEO_GIRO[i] * (1 - f) + SERVO_PARPADEO_GIRO[i + 1] * f;
}

static float aMicros(const Eje& e, float grados_servo) {
  float us = e.cal->us_centro + e.cal->sentido * grados_servo * e.cal->us_por_grado;
  return limitar(us, US_MIN, US_MAX);
}

static void escribir(Eje& e, float grados_servo) {
  e.servo.writeMicroseconds((int)(e.crudo ? limitar(e.us_crudo, US_MIN, US_MAX) : aMicros(e, grados_servo)));
}

static void mover(Eje& e, float dt) {
  float paso = e.vel * dt, d = e.objetivo - e.actual;
  e.actual += limitar(d, -paso, paso);
}

// ------------------------------------------------------------------ comportamiento
bool automatico = true;
float apertura_base = APERTURA_REPOSO;     // párpado "despierto" (sin contar parpadeos)
enum class Parpadeo { NO, CERRANDO, CERRADO, ABRIENDO } fase = Parpadeo::NO;
uint32_t t_fase = 0, t_prox_parpadeo = 0, t_prox_sacada = 0;

static void parpadear() {
  if (fase == Parpadeo::NO) { fase = Parpadeo::CERRANDO; t_fase = millis(); }
}

static void fijarMirada(float y, float p) {
  yaw.objetivo = limitar(y, -YAW_MAX, YAW_MAX);
  pitch.objetivo = limitar(p, -PITCH_MAX, PITCH_MAX);
}

static void actualizarParpado() {
  // el párpado acompaña a la mirada vertical: mirar arriba abre más, mirar abajo cierra un poco
  float abierto = limitar(apertura_base + SEGUIMIENTO_PARPADO * pitch.actual, 8, PARPADO_MAX_DEG);
  uint32_t t = millis() - t_fase;
  switch (fase) {
    case Parpadeo::NO:       parpado.vel = 400; parpado.objetivo = abierto; break;
    case Parpadeo::CERRANDO: parpado.vel = 700; parpado.objetivo = 0;
                             if (parpado.actual <= 0.5f || t > 250) { fase = Parpadeo::CERRADO; t_fase = millis(); } break;
    case Parpadeo::CERRADO:  if (t > 60) { fase = Parpadeo::ABRIENDO; t_fase = millis(); } break;
    case Parpadeo::ABRIENDO: parpado.vel = 450; parpado.objetivo = abierto;
                             if (fabsf(parpado.actual - abierto) < 0.5f || t > 300) fase = Parpadeo::NO; break;
  }
}

static void autonomo() {
  uint32_t ahora = millis();
  if (ahora >= t_prox_sacada) {
    // sacada: casi siempre cerca del centro, a veces a los extremos
    float r = random(0, 100) < 75 ? 0.45f : 1.0f;
    fijarMirada(random(-100, 101) / 100.0f * YAW_MAX * r, random(-100, 101) / 100.0f * PITCH_MAX * r);
    yaw.vel = pitch.vel = 300;
    t_prox_sacada = ahora + random(SACADA_MIN_MS, SACADA_MAX_MS);
    if (random(0, 100) < 20) parpadear();      // a veces se parpadea al mover la mirada
  }
  if (ahora >= t_prox_parpadeo) {
    parpadear();
    t_prox_parpadeo = ahora + random(PARPADEO_MIN_MS, PARPADEO_MAX_MS);
  }
}

// ------------------------------------------------------------------ web
WebServer web(80);

static String estado() {
  char b[200];
  snprintf(b, sizeof b, "{\"yaw\":%.1f,\"pitch\":%.1f,\"parpado\":%.1f,\"auto\":%s}", yaw.objetivo, pitch.objetivo,
           apertura_base, automatico ? "true" : "false");
  return String(b);
}

static void rutasWeb() {
  web.on("/", [] { web.send_P(200, "text/html; charset=utf-8", PAGINA); });
  web.on("/estado", [] { web.send(200, "application/json", estado()); });
  web.on("/mover", [] {
    automatico = false;
    if (web.hasArg("yaw") || web.hasArg("pitch"))
      fijarMirada(web.hasArg("yaw") ? web.arg("yaw").toFloat() : yaw.objetivo,
                  web.hasArg("pitch") ? web.arg("pitch").toFloat() : pitch.objetivo);
    if (web.hasArg("parpado")) apertura_base = limitar(web.arg("parpado").toFloat(), 0, PARPADO_MAX_DEG);
    yaw.vel = pitch.vel = 200;
    web.send(200, "application/json", estado());
  });
  web.on("/auto", [] {
    automatico = web.arg("on") == "1";
    if (automatico) apertura_base = APERTURA_REPOSO;
    web.send(200, "application/json", estado());
  });
  web.on("/parpadear", [] { parpadear(); web.send(200, "application/json", estado()); });
}

// ------------------------------------------------------------------ consola serie (calibración)
static Eje* ejePorNombre(const String& n) {
  if (n == "yaw") return &yaw;
  if (n == "pitch") return &pitch;
  if (n == "parpadeo") return &parpado;
  return nullptr;
}

static void consola() {
  if (!Serial.available()) return;
  String l = Serial.readStringUntil('\n'); l.trim();
  int sp = l.indexOf(' ');
  String c = sp < 0 ? l : l.substring(0, sp), a = sp < 0 ? "" : l.substring(sp + 1);
  if (c == "y" || c == "p") {
    automatico = false; yaw.crudo = pitch.crudo = false;
    fijarMirada(c == "y" ? a.toFloat() : yaw.objetivo, c == "p" ? a.toFloat() : pitch.objetivo);
  } else if (c == "b") {
    automatico = false; parpado.crudo = false; apertura_base = limitar(a.toFloat(), 0, PARPADO_MAX_DEG);
  } else if (c == "us") {                       // us <yaw|pitch|parpadeo> <µs> : pulso crudo para calibrar
    int s2 = a.indexOf(' ');
    Eje* e = ejePorNombre(a.substring(0, s2));
    if (e && s2 > 0) { automatico = false; e->crudo = true; e->us_crudo = a.substring(s2 + 1).toFloat(); }
  } else if (c == "auto") {
    automatico = a.toInt() != 0; yaw.crudo = pitch.crudo = parpado.crudo = false;
  } else if (c == "parpadea") {
    parpadear();
  } else if (c == "estado") {
    Serial.println(estado());
  } else {
    Serial.println(F("comandos: y <±30>  p <±25>  b <0..60 apertura>  parpadea  auto <0|1>  estado\n"
                     "          us <yaw|pitch|parpadeo> <500..2500>  (pulso crudo para calibrar, ver docs/MONTAJE.md)"));
    return;
  }
  Serial.println(estado());
}

// ------------------------------------------------------------------ arranque y bucle
void setup() {
  Serial.begin(115200);
  ESP32PWM::allocateTimer(0);
  const int pines[3] = {PIN_YAW, PIN_PITCH, PIN_PARPADEO};
  Eje* ejes[3] = {&yaw, &pitch, &parpado};
  const CalServo* cal[3] = {&CAL_YAW, &CAL_PITCH, &CAL_PARPADEO};
  for (int i = 0; i < 3; i++) {
    ejes[i]->cal = cal[i];
    ejes[i]->servo.setPeriodHertz(50);
    ejes[i]->servo.attach(pines[i], (int)US_MIN, (int)US_MAX);
  }
  // arranque: mirada al frente y párpados cerrados (la posición de montaje)
  escribir(yaw, 0); escribir(pitch, 0); escribir(parpado, giroParpadeo(0));
  randomSeed(esp_random());
  WiFi.mode(WIFI_AP);
  WiFi.softAP(WIFI_SSID, WIFI_CLAVE);
  rutasWeb();
  web.begin();
  Serial.printf("Ojo listo. WiFi \"%s\" → http://%s   (escribe \"ayuda\")\n", WIFI_SSID, WiFi.softAPIP().toString().c_str());
  t_prox_parpadeo = millis() + 1500;
  t_prox_sacada = millis() + 1000;
}

void loop() {
  static uint32_t t_ant = millis();
  web.handleClient();
  consola();
  uint32_t ahora = millis();
  if (ahora - t_ant < 10) return;               // 100 Hz
  float dt = (ahora - t_ant) / 1000.0f; t_ant = ahora;
  if (automatico) autonomo();
  actualizarParpado();
  mover(yaw, dt); mover(pitch, dt); mover(parpado, dt);
  escribir(yaw, yaw.actual);
  escribir(pitch, pitch.actual);
  escribir(parpado, giroParpadeo(parpado.actual));
}
