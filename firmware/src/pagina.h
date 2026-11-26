// Página de control servida por el ESP32 (sin dependencias externas: funciona sin Internet).
#pragma once
#include <pgmspace.h>

const char PAGINA[] PROGMEM = R"HTML(<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ojo animatrónico</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:16px;background:#111;color:#eee}
 h1{font-size:1.3em} label{display:block;margin-top:18px} input[type=range]{width:100%}
 button{margin:16px 8px 0 0;padding:12px 18px;font-size:1em;border:0;border-radius:8px;background:#2d6cdf;color:#fff}
 #pad{margin-top:18px;width:100%;aspect-ratio:1.2;background:#222;border-radius:12px;position:relative;touch-action:none}
 #punto{position:absolute;width:22px;height:22px;border-radius:50%;background:#2d6cdf;transform:translate(-50%,-50%)}
 small{color:#999}
</style></head><body>
<h1>Ojo animatrónico Ø150</h1>
<small>Arrastra en el recuadro para mirar. Yaw ±30°, pitch ±25°.</small>
<div id="pad"><div id="punto"></div></div>
<label>Párpado: <span id="vp"></span>°<input id="parpado" type="range" min="0" max="60" step="1"></label>
<button onclick="api('/parpadear')">Parpadear</button>
<button id="bauto" onclick="api('/auto?on='+(auto?0:1))"></button>
<script>
let auto=true, ult=0;
const pad=document.getElementById('pad'), punto=document.getElementById('punto'), par=document.getElementById('parpado');
function pinta(e){auto=e.auto;document.getElementById('bauto').textContent=auto?'Pasar a manual':'Modo automático';
 punto.style.left=(50+e.yaw/30*50)+'%';punto.style.top=(50-e.pitch/25*50)+'%';par.value=e.parpado;
 document.getElementById('vp').textContent=Math.round(e.parpado);}
function api(u){fetch(u).then(r=>r.json()).then(pinta);}
function mueve(ev){const r=pad.getBoundingClientRect();
 const x=Math.max(-1,Math.min(1,((ev.clientX-r.left)/r.width)*2-1)), y=Math.max(-1,Math.min(1,1-((ev.clientY-r.top)/r.height)*2));
 const t=Date.now(); if(t-ult<60)return; ult=t; api('/mover?yaw='+(x*30).toFixed(1)+'&pitch='+(y*25).toFixed(1));}
pad.addEventListener('pointerdown',e=>{pad.setPointerCapture(e.pointerId);mueve(e);});
pad.addEventListener('pointermove',e=>{if(e.buttons)mueve(e);});
par.addEventListener('input',()=>api('/mover?parpado='+par.value));
api('/estado'); setInterval(()=>{if(auto)api('/estado');},1500);
</script></body></html>)HTML";
