// GENERADO por herramientas/tabla_parpadeo.py — no editar a mano.
// Giro del servo de parpadeo (grados, respecto a la posición de párpados cerrados) para una apertura
// del párpado superior de 0..60° (índice = grados). Párpado inferior real a 60°: 59.83°.
#pragma once
constexpr int PARPADO_MAX_DEG = 60;
constexpr float SERVO_PARPADEO_GIRO[61] = {
  -0.000f, 1.139f, 2.271f, 3.398f, 4.521f, 5.641f, 6.758f, 7.872f,
  8.985f, 10.097f, 11.209f, 12.320f, 13.433f, 14.546f, 15.661f, 16.778f,
  17.897f, 19.019f, 20.143f, 21.272f, 22.403f, 23.539f, 24.679f, 25.824f,
  26.973f, 28.128f, 29.288f, 30.454f, 31.626f, 32.803f, 33.987f, 35.178f,
  36.375f, 37.579f, 38.791f, 40.009f, 41.236f, 42.469f, 43.711f, 44.960f,
  46.217f, 47.483f, 48.757f, 50.039f, 51.330f, 52.629f, 53.936f, 55.253f,
  56.578f, 57.911f, 59.254f, 60.605f, 61.964f, 63.333f, 64.709f, 66.094f,
  67.488f, 68.889f, 70.299f, 71.716f, 73.141f,
};
