"""Radar RWA v6: CoinGecko (fondos tokenizados) + DefiLlama (RWA en DeFi).

Uso (en la carpeta "radar rwa"):
    python radar_rwa_v6.py

La primera vez te pide tu clave de CoinGecko y la guarda en clave.txt
(no la compartas ni la subas a ningun sitio). Si existe fondos_manual.json,
se muestra aparte como complemento de lo que CoinGecko no cubre.
No esta probado contra la API real: pegame lo que imprime.
"""
import json
import os
import time
import webbrowser
from datetime import date

import requests

CG = "https://api.coingecko.com/api/v3"
DEFILLAMA = "https://api.llama.fi/protocols"
CLAVE_ARCHIVO = "clave.txt"
MANUAL = "fondos_manual.json"
SALIDA = "radar.html"

CATEGORIAS = [
    ("tokenized-treasuries", "Bonos del Tesoro tokenizados"),
    ("tokenized-money-market-fund-mmfs", "Fondos monetarios tokenizados"),
    ("tokenized-private-credit", "Crédito privado tokenizado"),
    ("tokenized-gold", "Oro tokenizado"),
]
UMBRAL_PRECIO_FONDO = 1.0  # % en 7 dias: en un fondo de bonos el precio casi no se mueve
UMBRAL_SUBIDA = 3.0
UMBRAL_CAIDA = -1.5
TVL_PEQUENO = 200_000_000


def es(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def cargar_clave():
    k = os.environ.get("COINGECKO_API_KEY", "").strip()
    if k:
        return k
    if os.path.exists(CLAVE_ARCHIVO):
        with open(CLAVE_ARCHIVO, encoding="utf-8") as f:
            k = f.read().strip()
        if k:
            return k
    if os.environ.get("CI"):
        raise SystemExit("Falta COINGECKO_API_KEY en el entorno.")
    k = input("Pega tu clave de CoinGecko y pulsa Enter: ").strip()
    with open(CLAVE_ARCHIVO, "w", encoding="utf-8") as f:
        f.write(k)
    print(f"Clave guardada en {CLAVE_ARCHIVO}.")
    return k


def categoria_coingecko(clave, cat):
    r = requests.get(
        CG + "/coins/markets",
        headers={"x-cg-demo-api-key": clave},
        params={"vs_currency": "usd", "category": cat, "order": "market_cap_desc",
                "per_page": 10, "page": 1, "price_change_percentage": "7d"},
        timeout=30,
    )
    r.raise_for_status()
    time.sleep(2.5)  # limite del plan gratuito
    return [
        {"nombre": c.get("name"), "simbolo": (c.get("symbol") or "").upper(),
         "mcap_mm": round((c.get("market_cap") or 0) / 1e9, 3),
         "precio": c.get("current_price"),
         "cambio7d": c.get("price_change_percentage_7d_in_currency")}
        for c in r.json()
    ]


def datos_coingecko(clave):
    secciones, alertas = [], []
    for cat, titulo in CATEGORIAS:
        try:
            items = categoria_coingecko(clave, cat)
            error = None
        except Exception as e:  # noqa: BLE001
            items, error = [], str(e)
            print(f"  Aviso: no se pudo leer {cat}: {e}")
        secciones.append({"titulo": titulo, "categoria": cat, "items": items, "error": error})
        if cat in ("tokenized-treasuries", "tokenized-money-market-fund-mmfs"):
            for it in items:
                c = it["cambio7d"]
                if c is not None and it["mcap_mm"] >= 0.05 and abs(c) >= UMBRAL_PRECIO_FONDO:
                    alertas.append({"nivel": "medio", "texto":
                        f"{it['nombre']} ({it['simbolo']}): su precio varía un {es(c)} % en 7 días. "
                        "En un fondo de bonos suele ser casi plano; revisa la causa."})
    return secciones, alertas


def datos_defillama():
    r = requests.get(DEFILLAMA, timeout=30)
    r.raise_for_status()
    rwa = [p for p in r.json() if (p.get("category") or "").upper() == "RWA" and p.get("tvl")]
    rwa.sort(key=lambda p: p["tvl"], reverse=True)
    top = rwa[:10]
    alertas = []
    for p in top:
        c = p.get("change_7d")
        if c is None:
            continue
        if c <= UMBRAL_CAIDA:
            extra = " Su tamaño es pequeño." if p["tvl"] < TVL_PEQUENO else ""
            alertas.append({"nivel": "alto", "texto": f"{p['name']}: cae un {es(abs(c))} % en 7 días.{extra}"})
        elif c >= UMBRAL_SUBIDA:
            alertas.append({"nivel": "medio", "texto": f"{p['name']}: sube un {es(c)} % en 7 días. Revisa la causa."})
    auto = {"total_mm": round(sum(p["tvl"] for p in rwa) / 1e9, 2), "n": len(rwa),
            "activos": [{"nombre": p["name"], "valor_mm": round(p["tvl"] / 1e9, 2),
                         "semana_pct": round(p["change_7d"], 2) if p.get("change_7d") is not None else None,
                         "cadenas": p.get("chains", [])[:3]} for p in top]}
    return auto, alertas


PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radar RWA</title>
<style>
:root{--bg:#F3F5F4;--panel:#fff;--ink:#14232B;--mute:#5E6F77;--line:#D9E0DE;--acc:#0F6B63;--up:#1B7F4B;--down:#B3422F;--warn:#8A5A00;--tint:#E6F0EE;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0E1A1F;--panel:#152429;--ink:#E4ECEA;--mute:#93A5AB;--line:#264047;--acc:#4FC3B5;--up:#5CCB8B;--down:#F08A74;--warn:#E5B04A;--tint:#1A3A3A;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:400 15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums}
main{max-width:900px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:0 0 10px}
.sub{color:var(--mute);margin:0 0 6px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;margin-top:16px}
.big{font-size:34px;font-weight:700;line-height:1.1}
.up{color:var(--up)}.down{color:var(--down)}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:480px}
th,td{padding:8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--mute);font-size:13px;font-weight:600}
td small{display:block;color:var(--mute);font-size:12px}
.bar{height:6px;border-radius:3px;background:var(--acc);margin-top:5px;min-width:2px}
.tag{display:inline-block;border-radius:5px;padding:1px 7px;font-size:12px;font-weight:600;background:var(--tint);color:var(--warn);margin-left:6px}
.alerts{list-style:none;margin:0;padding:0}
.alerts li{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--line)}
.alerts li:last-child{border-bottom:0}
.dot{flex:none;width:10px;height:10px;border-radius:50%;margin-top:7px}
.note{color:var(--mute);font-size:13px;margin-top:10px}
</style></head><body><main>
<h1>Radar del mercado tokenizado</h1>
<p class="sub" id="gen"></p>
<div id="cg"></div>
<section class="panel" id="manual" hidden><h2>Fondos no cubiertos por CoinGecko (manual)</h2>
<div class="scroll"><table><thead><tr><th>Fondo</th><th>Valor (mm $)</th><th>Dato de</th><th>Fuente</th></tr></thead><tbody id="man"></tbody></table></div>
<p class="note">Datos introducidos a mano en fondos_manual.json. Si un dato tiene más de 30 días, aparece como antiguo.</p></section>
<section class="panel"><h2>RWA en DeFi (DefiLlama)</h2>
<div class="big" id="tot"></div><p class="note" id="totn"></p>
<div class="scroll"><table><thead><tr><th>Activo</th><th>Valor (mm $)</th><th>Semana</th></tr></thead><tbody id="auto"></tbody></table></div>
<p class="note">El cambio semanal mide entradas y salidas de dinero en el protocolo, no el precio.</p></section>
<section class="panel"><h2>Alertas</h2><ul class="alerts" id="al"></ul></section>
</main>
<script>
var D = __DATA__;
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function f(x,d){return x==null?"–":x.toFixed(d).replace(".",",")}
function sg(x){return x==null?"–":(x>0?"+":"")+f(x,1)+" %"}
function cl(x){return x==null?"":x>=0?"up":"down"}
document.getElementById("gen").textContent="Generado el "+D.generado+". Fuentes: CoinGecko y DefiLlama.";
document.getElementById("cg").innerHTML=D.cg.map(function(s){
  var mx=Math.max.apply(null,s.items.map(function(i){return i.mcap_mm}).concat([0.001]));
  var filas=s.items.length?s.items.map(function(i){
    return "<tr><td>"+esc(i.nombre)+"<small>"+esc(i.simbolo)+'</small><div class="bar" style="width:'+(i.mcap_mm/mx*100).toFixed(0)+'%"></div></td><td>'+f(i.mcap_mm,2)+"</td><td>"+(i.precio==null?"–":"$"+f(i.precio,i.precio<10?4:2))+'</td><td class="'+cl(i.cambio7d)+'">'+sg(i.cambio7d)+"</td></tr>"}).join(""):'<tr><td colspan="4">Sin datos'+(s.error?" ("+esc(s.error)+")":"")+"</td></tr>";
  return '<section class="panel"><h2>'+esc(s.titulo)+'</h2><div class="scroll"><table><thead><tr><th>Token</th><th>Capitalización (mm $)</th><th>Precio</th><th>Precio 7 d</th></tr></thead><tbody>'+filas+"</tbody></table></div></section>"}).join("");
if(D.manual.length){
  document.getElementById("manual").hidden=false;
  var hoy=new Date(D.generado);
  document.getElementById("man").innerHTML=D.manual.map(function(r){
    var v="";
    if(r.fecha){var d=(hoy-new Date(r.fecha))/86400000;if(d>30)v='<span class="tag">antiguo</span>';}else v='<span class="tag">sin dato</span>';
    return "<tr><td>"+esc(r.nombre)+"<small>"+esc(r.emisor)+"</small></td><td>"+f(r.valor_mm,2)+"</td><td>"+esc(r.fecha||"–")+v+"</td><td>"+esc(r.fuente||"–")+"</td></tr>"}).join("");
}
document.getElementById("tot").textContent=f(D.auto.total_mm,2)+" mm $";
document.getElementById("totn").textContent="Suma de "+D.auto.n+" protocolos RWA con valor en DefiLlama.";
var mx2=Math.max.apply(null,D.auto.activos.map(function(a){return a.valor_mm}).concat([0.001]));
document.getElementById("auto").innerHTML=D.auto.activos.map(function(a){
  return "<tr><td>"+esc(a.nombre)+"<small>"+esc((a.cadenas||[]).join(", "))+'</small><div class="bar" style="width:'+(a.valor_mm/mx2*100).toFixed(0)+'%"></div></td><td>'+f(a.valor_mm,2)+'</td><td class="'+cl(a.semana_pct)+'">'+sg(a.semana_pct)+"</td></tr>"}).join("");
document.getElementById("al").innerHTML=D.alertas.length?D.alertas.map(function(a){
  var col=a.nivel==="alto"?"var(--down)":"var(--warn)";
  return '<li><span class="dot" style="background:'+col+'"></span><span>'+esc(a.texto)+"</span></li>"}).join(""):"<li>Sin alertas esta semana.</li>";
</script></body></html>
"""


def construir_html(cg, auto, manual, alertas):
    datos = {"generado": date.today().isoformat(), "cg": cg, "auto": auto,
             "manual": manual, "alertas": alertas}
    return PAGINA.replace("__DATA__", json.dumps(datos, ensure_ascii=False))


def main():
    clave = cargar_clave()
    print("Descargando CoinGecko (tarda cerca de 15 segundos)...")
    cg, alertas_cg = datos_coingecko(clave)
    print("Descargando DefiLlama...")
    auto, alertas_dl = datos_defillama()
    manual = []
    if os.path.exists(MANUAL):
        with open(MANUAL, encoding="utf-8") as f:
            manual = json.load(f)
    alertas = alertas_cg + alertas_dl
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(construir_html(cg, auto, manual, alertas))
    print("\nResumen CoinGecko:")
    for s in cg:
        print(f"  {s['titulo']}: {len(s['items'])} tokens" + (f" (error: {s['error']})" if s["error"] else ""))
        for it in s["items"][:3]:
            print(f"     {it['nombre']} ({it['simbolo']}): {it['mcap_mm']} mm $")
    print(f"\nRWA en DeFi: {auto['total_mm']} mm $ en {auto['n']} protocolos | alertas: {len(alertas)}")
    ruta = os.path.abspath(SALIDA)
    print(f"Listo: {ruta}")
    if not os.environ.get("CI"):
        webbrowser.open("file:///" + ruta.replace("\\", "/"))


if __name__ == "__main__":
    main()
