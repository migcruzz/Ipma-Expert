import difflib
import inspect
import os
import uuid

import aiohttp
import plotly.graph_objs as go
import plotly.io as pio
from quart import Quart, request, render_template

BASE_URL = "https://api.ipma.pt/open-data"

# Directory Configs
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

app = Quart(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)


# Layer 1: api call
async def fetch_json(session, path: str) -> dict:
    url = f"{BASE_URL}{path}"
    async with session.get(url) as resp:
        resp.raise_for_status()
        return await resp.json()


EMOJI_MAP = {
    "Céu limpo": "☀️",
    "Céu pouco nublado": "⛅",
    "Céu parcialmente nublado": "⛅",
    "Céu muito nublado ou encoberto": "☁️",
    "Céu nublado por nuvens altas": "☁️",
    "Céu com períodos de muito nublado": "☁️",
    "Céu nublado": "☁️",
    "Aguaceiros/chuva": "🌧️",
    "Aguaceiros/chuva fracos": "🌦️",
    "Aguaceiros/chuva fortes": "⛈️",
    "Chuva/aguaceiros": "🌧️",
    "Chuva fraca ou chuvisco": "🌦️",
    "Chuva/aguaceiros forte": "⛈️",
    "Períodos de chuva": "🌧️",
    "Períodos de chuva fraca": "🌦️",
    "Períodos de chuva forte": "⛈️",
    "Chuvisco": "🌦️",
    "Neblina": "🌫️",
    "Nevoeiro ou nuvens baixas": "🌫️",
    "Nevoeiro": "🌫️",
    "Neve": "❄️",
    "Aguaceiros de neve": "🌨️",
    "Chuva e Neve": "🌨️",
    "Trovoada": "⛈️",
    "Aguaceiros e possibilidade de trovoada": "⛈️",
    "Chuva e possibilidade de trovoada": "⛈️",
    "Granizo": "🌨️",
    "Geada": "🧊",
    "Nebulosidade convectiva": "☁️",
}


# Layer 2: pré-processing
async def extract_city(session, text: str):
    lower = text.lower()
    data = await fetch_json(session, "/distrits-islands.json")
    for loc in data["data"]:
        if loc["local"].lower() in lower:
            return loc["local"]
    # fuzzy match
    names = [loc["local"] for loc in data["data"]]
    match = difflib.get_close_matches(lower, [n.lower() for n in names], n=1, cutoff=0.6)
    if match:
        matched = match[0]
        for loc in data["data"]:
            if loc["local"].lower() == matched:
                return loc["local"]
    return None


PREPROCESSORS = {
    "cidade": extract_city,
    "incluir_grafico": lambda s, t: "gráfico" in t.lower() or "grafico" in t.lower(),
    "intencao_previsao": lambda s, t: any(kw in t.lower() for kw in ("tempo", "previsão")),
    "mostrar_mapa": lambda s, t: "mapa" in t.lower(),
    "todas_localidades": lambda s, t: any(
        kw in t.lower() for kw in ("todas as cidades", "todas localidades", "all cities")),
}


async def parse_user_input(session, text: str) -> dict:
    out = {}
    for flag, fn in PREPROCESSORS.items():
        if inspect.iscoroutinefunction(fn):
            out[flag] = await fn(session, text)
        else:
            res = fn(session, text)
            out[flag] = await res if inspect.iscoroutine(res) else res
    return out


# Layer 3: data providers
async def provider_locations(session, parsed):
    return (await fetch_json(session, "/distrits-islands.json"))["data"]


async def provider_forecast(session, parsed):
    gid = parsed["global_id"]
    return (await fetch_json(session, f"/forecast/meteorology/cities/daily/{gid}.json"))["data"]


async def provider_weather_types(session, parsed):
    return (await fetch_json(session, "/weather-type-classe.json"))["data"]


async def provider_precipitation(session, parsed):
    return (await fetch_json(session, "/precipitation-classe.json"))["data"]


DATA_PROVIDERS = {
    "locations": provider_locations,
    "forecast": provider_forecast,
    "weather_types": provider_weather_types,
    "precipitation": provider_precipitation,
}


async def gather_data(session, parsed) -> dict:
    out = {}
    for key, fn in DATA_PROVIDERS.items():
        out[key] = await fn(session, parsed)
    return out


# Layer 4: data transformation
def format_day(day, types, precs):
    desc = next((w["descWeatherTypePT"] for w in types if w["idWeatherType"] == day["idWeatherType"]), "Desconhecido")
    cpi = day.get("classPrecInt")
    pdesc = next((p["descClassPrecIntPT"] for p in precs if str(p["classPrecInt"]) == str(cpi)),
                 "Sem dados") if cpi is not None else "Sem dados"
    return {
        "data": day["forecastDate"],
        "temperatura_min": day["tMin"],
        "temperatura_max": day["tMax"],
        "vento": day["predWindDir"],
        "tipo_tempo": desc,
        "precipitacao": pdesc,
        "prob_precipitacao": day.get("precitaProb", day.get("precipitaProb", "0")),
        "emoji": EMOJI_MAP.get(desc, "")
    }


# Layer 5: plot generator
def generate_plot(forecast_data):
    dates = [d["forecastDate"] for d in forecast_data]
    tmin = [float(d["tMin"]) for d in forecast_data]
    tmax = [float(d["tMax"]) for d in forecast_data]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=tmin, name="T. Mínima", mode="lines+markers"))
    fig.add_trace(go.Scatter(x=dates, y=tmax, name="T. Máxima", mode="lines+markers"))
    fig.update_layout(title="Previsão de Temperatura", xaxis_title="Data", yaxis_title="°C")
    return pio.to_html(fig, full_html=False, include_plotlyjs="cdn")


# Layer 6: map and pointer with meteorology
def generate_map(lat: float, lon: float, popup: str) -> str:
    map_id = f"map-{uuid.uuid4().hex}"
    return f"""
<div id="{map_id}" style="height:300px;"></div>
<script>
  (function() {{
    var map = L.map('{map_id}').setView([{lat}, {lon}], 10);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '© OpenStreetMap contributors'
    }}).addTo(map);
    L.marker([{lat}, {lon}])
      .addTo(map)
      .bindPopup({popup!r})
      .openPopup();
  }})();
</script>
"""


# Layer 7: multi map and pointer with meteorology
def generate_map_all(locations, forecasts) -> str:
    map_id = f"map-{uuid.uuid4().hex}"
    center_lat, center_lon, zoom = 39.5, -8.0, 7
    html = f"""
<div id="{map_id}" style="height:500px;"></div>
<script>
  (function() {{
    var map = L.map('{map_id}').setView([{center_lat}, {center_lon}], {zoom});
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '© OpenStreetMap contributors'
    }}).addTo(map);
"""
    for loc in locations:
        gid = loc["globalIdLocal"]
        lat = float(loc["latitude"])
        lon = float(loc["longitude"])
        f = forecasts.get(gid, {})
        popup = loc["local"]
        if f:
            popup += f" — {f['emoji']} {f['tipo_tempo']} {f['temperatura_min']}°C–{f['temperatura_max']}°C"
        html += f"    L.marker([{lat}, {lon}]).addTo(map).bindPopup({popup!r});\n"
    html += "  })();</script>"
    return html


# Layer 8: prompt + mistral
def build_prompt(cidade, hoje):
    return (
        f"Cidade: {cidade}\n"
        f"Data: {hoje['data']}\n"
        f"Tempo: {hoje['tipo_tempo']} {hoje['emoji']}\n"
        f"Tª min: {hoje['temperatura_min']}°C\n"
        f"Tª max: {hoje['temperatura_max']}°C\n"
        f"Vento: {hoje['vento']}\n"
        f"Precipitação: {hoje['precipitacao']}\n"
        f"Prob.: {hoje['prob_precipitacao']}%\n\n"
        "Responde em português europeu, de forma simpática."
    )


async def call_mistral(session, prompt):
    async with session.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False}
    ) as resp:
        resp.raise_for_status()
        return (await resp.json())["response"].strip()


# routes
@app.route("/")
async def index():
    return await render_template("index.html")


@app.route("/chat", methods=["POST"])
async def chat_htmx():
    form = await request.form
    text = form.get("mensagem", "").strip()
    if not text:
        default = "Desculpa, não recebi nenhuma mensagem. Podes tentar novamente?"
        return await render_template(
            "response.html",
            user_message=text,
            resposta=default,
            grafico_html=None,
            map_html=None,
            plot_list=None
        )

    async with aiohttp.ClientSession() as session:
        flags = await parse_user_input(session, text)

        # all cities request
        if flags.get("todas_localidades"):
            locs = (await fetch_json(session, "/distrits-islands.json"))["data"]
            forecasts = {}
            plot_list = [] if flags.get("incluir_grafico") else None

            for loc in locs:
                gid = loc["globalIdLocal"]
                parsed = {**flags, "global_id": gid}
                data = await gather_data(session, parsed)

                resumo = format_day(data["forecast"][0], data["weather_types"], data["precipitation"])
                forecasts[gid] = resumo

                if flags.get("incluir_grafico"):
                    plot_list.append({
                        "local": loc["local"],
                        "html": generate_plot(data["forecast"])
                    })

            map_html = generate_map_all(locs, forecasts)
            return await render_template(
                "response.html",
                user_message=text,
                resposta="Mapa e gráficos de todas as cidades:",
                grafico_html=None,
                map_html=map_html,
                plot_list=plot_list
            )

        if not flags.get("cidade") or not flags.get("intencao_previsao"):
            default = "Desculpa, não consegui processar o teu pedido. Podes reformular indicando cidade e o que pretendes?"
            return await render_template(
                "response.html",
                user_message=text,
                resposta=default,
                grafico_html=None,
                map_html=None,
                plot_list=None
            )

        # resolve global_idLocal
        locs = (await fetch_json(session, "/distrits-islands.json"))["data"]
        obj = next((l for l in locs if l["local"].lower() == flags["cidade"].lower()), None)
        if not obj:
            default = f"Não encontrei '{flags['cidade']}'. Podes confirmar o nome?"
            return await render_template(
                "response.html",
                user_message=text,
                resposta=default,
                grafico_html=None,
                map_html=None,
                plot_list=None
            )
        flags["global_id"] = obj["globalIdLocal"]

        data = await gather_data(session, flags)
        hoje = format_day(data["forecast"][0], data["weather_types"], data["precipitation"])

        # calling LLM
        prompt = build_prompt(flags["cidade"], hoje)
        resposta = await call_mistral(session, prompt)

    graf_html = (generate_plot(data["forecast"]) if flags.get("incluir_grafico") else None)

    # popup
    popup_text = (
        f"{hoje['emoji']} {hoje['tipo_tempo']}, "
        f"{hoje['temperatura_min']}°C–{hoje['temperatura_max']}°C"
    )
    map_html = (generate_map(obj["latitude"], obj["longitude"], popup_text)
                if flags.get("mostrar_mapa") else None)

    return await render_template(
        "response.html",
        user_message=text,
        resposta=resposta,
        grafico_html=graf_html,
        map_html=map_html,
        plot_list=None
    )


if __name__ == "__main__":
    app.run(debug=True)
