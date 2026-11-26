// Configuración del ojo. Los LÍMITES salen de parametros/ojo.json ("movimiento") y están comprobados sin choques
// en herramientas/verificar.py: no los amplíes sin volver a verificar.
#pragma once

// ---- pines (ESP32 DevKitC; cualquier GPIO con salida PWM sirve) ----
constexpr int PIN_YAW = 13;        // servo dentro de la cuna: giro izquierda/derecha
constexpr int PIN_PITCH = 14;      // servo en la horquilla derecha: arriba/abajo
constexpr int PIN_PARPADEO = 27;   // servo trasero: balancín y bielas de los dos párpados

// ---- límites mecánicos (grados del movimiento del ojo, no del servo) ----
constexpr float YAW_MAX = 30.0f;     // ±
constexpr float PITCH_MAX = 25.0f;   // ±
// párpado: 0 = cerrado … PARPADO_MAX_DEG (60) = abierto del todo (ver parpadeo_tabla.h)

// ---- calibración de cada servo (ajustar con la consola serie, ver docs/MONTAJE.md) ----
struct CalServo {
  float us_centro;     // µs con el ojo al frente (yaw/pitch) o con los PÁRPADOS CERRADOS (parpadeo)
  float us_por_grado;  // MG90S ≈ 10 µs/° (500–2500 µs ≈ 0–200°); medir con un transportador si se quiere fino
  int sentido;         // +1 / -1 según cómo quede montado
};
// El parpadeo recorre 73,1° de servo. Se monta con los párpados cerrados a +36° del centro del servo, para que
// el recorrido quede centrado (1500 + 36,5·10 ≈ 1865 µs cerrado → ≈ 1135 µs abierto).
constexpr CalServo CAL_YAW = {1500.0f, 10.0f, +1};
constexpr CalServo CAL_PITCH = {1500.0f, 10.0f, +1};
constexpr CalServo CAL_PARPADEO = {1865.0f, 10.0f, -1};
constexpr float US_MIN = 500.0f, US_MAX = 2500.0f;   // nunca se manda nada fuera

// ---- comportamiento autónomo ----
constexpr float APERTURA_REPOSO = 48.0f;        // párpado "despierto" (grados)
constexpr float SEGUIMIENTO_PARPADO = 0.6f;     // el párpado acompaña a la mirada vertical (como un ojo real)
constexpr uint32_t PARPADEO_MIN_MS = 2000, PARPADEO_MAX_MS = 6000;
constexpr uint32_t SACADA_MIN_MS = 700, SACADA_MAX_MS = 3500;

// ---- WiFi (punto de acceso propio; página de control en http://192.168.4.1) ----
constexpr const char* WIFI_SSID = "OjoAnimatronico";
constexpr const char* WIFI_CLAVE = "cambia-esta-clave";   // mínimo 8 caracteres
