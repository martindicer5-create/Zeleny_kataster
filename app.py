"""
Zelený kataster – Streamlit webová aplikácia
Pilotné územie: k.ú. Zuberec, Žilinský kraj
Verzia: bez databázy (súbory GeoJSON + CSV)
"""

import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
import plotly.express as px

st.set_page_config(page_title="Zelený kataster – Zuberec",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
    background-color: #1a3d25 !important; }
[data-testid="stSidebar"] * { color: #d4e8d4 !important; }
[data-testid="stSidebar"] hr { border-color: #3d6e47 !important; }
.banner { background: linear-gradient(135deg, #1e4d2b 0%, #2d7a3a 100%);
    color: white; padding: 1.8rem 2.2rem; border-radius: 14px;
    margin-bottom: 1.6rem; box-shadow: 0 4px 20px rgba(0,0,0,0.15); }
.banner h1 { margin:0; font-weight:700; font-size:1.9rem; color:white; }
.banner p  { margin:6px 0 0; opacity:.7; font-size:.9rem; }
[data-testid="stMetric"] { background: white; padding: 16px 20px;
    border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    border: 1px solid #eef0f3; }
[data-testid="stMetricLabel"]  { font-size: .8rem !important; font-weight:600;
    color:#6b7280 !important; text-transform:uppercase; letter-spacing:.5px; }
[data-testid="stMetricValue"]  { font-size: 1.6rem !important; font-weight:700;
    color:#111827 !important; }
.stButton>button { border-radius: 8px; font-weight:600; letter-spacing:.3px; }
[data-baseweb="tab-list"] { gap: 4px; border-bottom: 2px solid #e5e7eb; }
[data-baseweb="tab"] { font-size:.9rem; font-weight:500;
    border-radius:8px 8px 0 0; padding:8px 16px; }
.nice-table { width:100%; border-collapse:collapse; font-size:.88rem; background:white; }
.nice-table thead tr { background:#1e4d2b; color:white; }
.nice-table thead th { padding:10px 14px; text-align:left; font-weight:600;
    font-size:.82rem; letter-spacing:.4px; text-transform:uppercase; color:white !important; }
.nice-table tbody tr { border-bottom:1px solid #f3f4f6; background:white; }
.nice-table tbody tr:hover { background:#f9fafb; }
.nice-table tbody td { padding:9px 14px; color:#111827 !important; background:white; }
.nice-table tbody tr:last-child { border-bottom:none; }
.table-wrap { border-radius:12px; overflow:hidden; border:1px solid #e5e7eb;
    box-shadow:0 1px 6px rgba(0,0,0,0.06); background:white; }
.badge { display:inline-block; padding:2px 10px; border-radius:20px;
    font-size:.78rem; font-weight:600; }
.badge-green  { background:#dcfce7; color:#16a34a; }
.badge-yellow { background:#fef9c3; color:#ca8a04; }
.badge-red    { background:#fee2e2; color:#dc2626; }
.badge-blue   { background:#dbeafe; color:#2563eb; }
.badge-gray   { background:#f3f4f6; color:#6b7280; }
</style>
""", unsafe_allow_html=True)

# ── Konštanty ──────────────────────────────────────────────────────────────
KULTURA_FARBA = {
    "orná pôda":            "#f59e0b",
    "trvalý trávny porast": "#22c55e",
    "vinica":               "#a855f7",
    "chmeľnica":            "#ec4899",
    "ovocný sad":           "#f97316",
    "lesný pozemok":        "#166534",
    "zastavané a nádvoria": "#94a3b8",
    "ostatná plocha":       "#cbd5e1",
}

KULTURA_BADGE = {
    "trvalý trávny porast": "badge-green",
    "orná pôda":            "badge-yellow",
    "lesný pozemok":        "badge-blue",
    "záhrada":              "badge-green",
    "ovocný sad":           "badge-yellow",
    "vodná plocha":         "badge-blue",
    "zastavané a nádvoria": "badge-gray",
    "ostatné plochy":       "badge-gray",
}

SYMBOL_MAP = {
    30:  "Orná pôda",        32:  "Trvalý trávny porast",
    34:  "Ovocný sad",       37:  "Vinica",
    40:  "Chmeľnica",        42:  "Záhrada",
    45:  "Lesný pozemok",   238:  "Vodný tok",
    239: "Vodná nádrž",     431:  "Dvor, stavebná plocha",
    432: "Cesta, komunikácia", 435: "Ostatná plocha",
    479: "Orná pôda",
}

ZHODY = {
    (30,"orná pôda"), (32,"trvalý trávny porast"),
    (34,"ovocný sad"), (37,"vinica"), (40,"chmeľnica"),
    (42,"záhrada"), (45,"lesný pozemok"),
    (238,"vodná plocha"), (239,"rybník"),
    (431,"zastavané a nádvoria"), (432,"ostatné plochy"),
    (479,"orná pôda"),
}

# ── Načítanie dát ──────────────────────────────────────────────────────────
@st.cache_data
def load_geojson():
    with open("prienik_zuberec.geojson", encoding="utf-8") as f:
        gj = json.load(f)

    # Load kn data to enrich GeoJSON with symbol and zhoda
    df = pd.read_csv("prienik_kn_lpis.csv")
    df["symbol"] = pd.to_numeric(df["symbol"], errors="coerce")
    df["kn_druh"] = df["symbol"].map(SYMBOL_MAP).fillna("Iné")
    df["cpa"] = df["cpa"].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) else "")
    # One KN druh per CPA (take first — symbol is same for all rows of same parcel)
    kn_lookup  = df.groupby("cpa")["kn_druh"].first().to_dict()
    sym_lookup = df.groupby("cpa")["symbol"].first().to_dict()

    for feat in gj["features"]:
        cpa = str(feat["properties"].get("CPA", "")).strip()
        kultura = (feat["properties"].get("KULTURA_NA") or "").lower()
        kn_druh = kn_lookup.get(cpa, "Neznámy")
        symbol  = sym_lookup.get(cpa)
        zhoda   = (int(symbol), kultura) in ZHODY if (symbol is not None and not pd.isna(symbol)) else True
        feat["properties"]["kn_druh"]      = kn_druh
        feat["properties"]["lpis_kultura"] = feat["properties"].get("KULTURA_NA", "")
        feat["properties"]["zhoda"]        = zhoda
    return gj

@st.cache_data
def load_kn_lpis():
    df = pd.read_csv("prienik_kn_lpis.csv")
    df["symbol"] = pd.to_numeric(df["symbol"], errors="coerce")
    df["ha"] = pd.to_numeric(df["ha"], errors="coerce")
    return df[["cpa", "symbol", "kultura_na", "ha"]].dropna(subset=["symbol"])

@st.cache_data
def load_master_final():
    df = pd.read_csv("master_final.csv", header=None)
    df.columns = ["id", "geom", "parcela_num", "fid2", "fid3",
                  "parcela", "lpis_nazov", "vymera_gis", "bpej"]
    df["vymera_gis"] = pd.to_numeric(df["vymera_gis"], errors="coerce")
    df["bpej"] = pd.to_numeric(df["bpej"], errors="coerce").astype("Int64")
    return df[["parcela", "bpej", "vymera_gis", "lpis_nazov"]].dropna(subset=["bpej"])

# ── Helper funkcie ─────────────────────────────────────────────────────────
def cpa_display(cpa):
    """Convert VGI CPA format (1283.001) to cadastral format (1283/1)."""
    s = str(cpa).strip()
    if "." in s:
        main, sub = s.split(".", 1)
        sub = sub.lstrip("0")
        return main if not sub else f"{main}/{sub}"
    return s


    rows = ""
    for _, r in df.head(max_rows).iterrows():
        cells = ""
        for col in df.columns:
            val = r[col]
            if badge_col and col == badge_col and badge_map:
                cls = badge_map.get(str(val).lower(), "badge-gray")
                cells += f'<td><span class="badge {cls}">{val}</span></td>'
            elif col in ["cpa", "Parcela KN", "CPA", "parcela", "Parcela"]:
                cells += f'<td>{val}</td>'
            elif isinstance(val, float):
                cells += f'<td>{val:,.4f}</td>' if val < 1 else f'<td>{val:,.2f}</td>'
            else:
                cells += f'<td>{val}</td>'
        rows += f"<tr>{cells}</tr>"
    headers = "".join(f"<th>{c}</th>" for c in df.columns)
    html = (f'<div class="table-wrap"><table class="nice-table">'
            f'<thead><tr>{headers}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')
    st.markdown(html, unsafe_allow_html=True)

def build_map(gj, center=(49.2630, 19.6330)):
    m = folium.Map(location=center, zoom_start=13,
                   tiles="CartoDB Positron", prefer_canvas=True)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="Satelit", overlay=False).add_to(m)
    folium.TileLayer("CartoDB Positron", name="Mapa", overlay=False).add_to(m)

    def style(f):
        zhoda = f["properties"].get("zhoda", True)
        return {
            "fillColor": "#22c55e" if zhoda else "#ef4444",
            "color":     "#14532d" if zhoda else "#7f1d1d",
            "weight": 0.6, "fillOpacity": 0.7
        }

    folium.GeoJson(gj, name="Prienik KN–LPIS", style_function=style,
        tooltip=folium.GeoJsonTooltip(
            fields=["CPA", "kn_druh", "lpis_kultura", "ha"],
            aliases=["Parcela KN:", "KN druh pozemku:", "LPIS kultúra:", "Výmera (ha):"],
        )).add_to(m)

    folium.LayerControl().add_to(m)
    return m

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
**Zelený kataster · Zuberec**
Integrácia KN – LPIS – BPEJ
QGIS + PostGIS + Streamlit
""")
    st.divider()
    st.markdown("""
**Dátové zdroje:**
- `prienik_zuberec.geojson`
- `prienik_kn_lpis.csv`
- `master_final.csv`
""")

# ── Banner ─────────────────────────────────────────────────────────────────
st.markdown("""<div class="banner">
  <h1>Zelený kataster</h1>
  <p>k.ú. Zuberec · Žilinský kraj · Integrácia KN – LPIS – BPEJ · QGIS + PostGIS</p>
</div>""", unsafe_allow_html=True)

# ── Načítaj dáta ──────────────────────────────────────────────────────────
try:
    gj = load_geojson()
    df_kn = load_kn_lpis()
    df_mf = load_master_final()
except FileNotFoundError as e:
    st.error(f"Chýba súbor: {e}. Uisti sa, že súbory sú v rovnakom priečinku ako app.py.")
    st.stop()

# ── KPI ────────────────────────────────────────────────────────────────────
n_poly  = len(df_kn)
n_parc  = df_kn["cpa"].nunique()
ha_total = df_kn["ha"].sum()
ha_ttp   = df_kn[df_kn["kultura_na"].str.lower() == "trvalý trávny porast"]["ha"].sum()
ha_op    = df_kn[df_kn["kultura_na"].str.lower() == "orná pôda"]["ha"].sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Polygónov",        f"{n_poly:,}")
c2.metric("Parciel KN",       f"{n_parc:,}")
c3.metric("Celková výmera",   f"{ha_total:,.2f} ha")
c4.metric("TTP (LPIS)",       f"{ha_ttp:,.2f} ha")
c5.metric("Orná pôda (LPIS)", f"{ha_op:,.2f} ha")

st.write("")

# ── Taby ───────────────────────────────────────────────────────────────────
tab_mapa, tab_stats, tab_disk, tab_bpej = st.tabs([
    "🗺️ Mapa", "📊 Štatistiky", "⚠️ Nesúlady KN↔LPIS", "🌱 Analýza BPEJ"
])

# ── TAB: MAPA ──────────────────────────────────────────────────────────────
with tab_mapa:
    col_m, col_leg = st.columns([4, 1])
    with col_m:
        feats = gj.get("features", [])
        st.caption(f"Zobrazených: **{len(feats):,}** polygónov · Najazdite kurzorom na plochu pre detail")
        st_folium(build_map(gj), width="100%", height=560, returned_objects=[])
    with col_leg:
        st.markdown("#### Legenda")
        st.markdown('<span style="color:#22c55e;font-size:1.5rem">■</span> Zhoda KN–LPIS', unsafe_allow_html=True)
        st.markdown('<span style="color:#ef4444;font-size:1.5rem">■</span> Nesúlad KN–LPIS', unsafe_allow_html=True)
        st.divider()
        st.caption("Klikni na plochu pre detail parcely.")

# ── TAB: ŠTATISTIKY ────────────────────────────────────────────────────────
with tab_stats:
    df_k = (df_kn.groupby("kultura_na")
            .agg(pocet=("cpa", "count"), ha=("ha", "sum"))
            .reset_index()
            .sort_values("ha", ascending=False))

    st.subheader("Výmera podľa kultúry LPIS")
    fig = px.bar(df_k, x="ha", y="kultura_na", orientation="h",
                 color="kultura_na", color_discrete_map=KULTURA_FARBA,
                 text="ha", labels={"ha": "Výmera (ha)", "kultura_na": ""})
    fig.update_traces(texttemplate="%{text:.1f} ha", textposition="inside",
                      insidetextanchor="end",
                      textfont=dict(size=13, color="white"),
                      marker_line_width=0)
    fig.update_layout(showlegend=False, plot_bgcolor="white",
                      paper_bgcolor="white",
                      font=dict(family="Inter", size=14, color="#111827"),
                      height=400, margin=dict(l=0, r=20, t=10, b=10),
                      xaxis=dict(tickfont=dict(color="#111827")),
                      yaxis=dict(tickfont=dict(color="#111827")))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Parcely s viacerými kultúrami LPIS")
    df_multi = (df_kn.groupby("cpa")
                .agg(pocet_kultur=("kultura_na", "nunique"),
                     kultury=("kultura_na", lambda x: " · ".join(sorted(set(x)))),
                     ha=("ha", "sum"))
                .reset_index()
                .query("pocet_kultur > 1")
                .sort_values("ha", ascending=False)
                .head(50))
    df_multi["cpa"] = df_multi["cpa"].apply(cpa_display)
    df_multi.columns = ["Parcela KN", "Počet kultúr", "Kultúry LPIS", "Výmera (ha)"]
    if not df_multi.empty:
        render_table(df_multi)
    else:
        st.info("Žiadne parcely s viacerými kultúrami.")

# ── TAB: NESÚLADY ──────────────────────────────────────────────────────────
with tab_disk:
    st.subheader("Nesúlady medzi katastrom a LPIS")

    df_agg = (df_kn.groupby(["symbol", "kultura_na"])
              .agg(ha=("ha", "sum")).reset_index())
    df_agg["kn_druh"] = df_agg["symbol"].map(SYMBOL_MAP).fillna("Iné")
    df_agg["zhoda"] = df_agg.apply(
        lambda r: (int(r["symbol"]), r["kultura_na"].lower()) in ZHODY, axis=1)

    zhody    = df_agg[df_agg["zhoda"]]
    nesulady = df_agg[~df_agg["zhoda"]]

    k1, k2, k3 = st.columns(3)
    k1.metric("Plocha v súlade",   f"{zhody['ha'].sum():.1f} ha")
    k2.metric("Plocha v nesúlade", f"{nesulady['ha'].sum():.1f} ha")
    pct = nesulady["ha"].sum() / df_agg["ha"].sum() * 100
    k3.metric("Podiel nesúladu",   f"{pct:.1f} %")

    st.divider()
    st.subheader("Typy nesúladov")
    if not nesulady.empty:
        plot_df = nesulady.copy().sort_values("ha")
        plot_df["label"] = plot_df["kn_druh"] + " → " + plot_df["kultura_na"]
        fig_d = px.bar(plot_df, x="ha", y="label", orientation="h",
                       color_discrete_sequence=["#ef4444"],
                       labels={"ha": "Výmera (ha)", "label": ""})
        fig_d.update_traces(marker_line_width=0)
        fig_d.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                            font=dict(family="Inter", size=14, color="#111827"),
                            height=max(220, len(plot_df)*52),
                            margin=dict(l=0, r=30, t=10, b=10),
                            xaxis=dict(tickfont=dict(color="#111827")),
                            yaxis=dict(tickfont=dict(color="#111827")))
        st.plotly_chart(fig_d, use_container_width=True)

    st.divider()
    st.subheader("Parcely s najväčším nesúladom")
    df_parc = df_kn[
        ~df_kn.apply(lambda r: (int(r["symbol"]), r["kultura_na"].lower()) in ZHODY, axis=1)
    ].copy()
    df_parc["KN druh pozemku"] = df_parc["symbol"].map(SYMBOL_MAP).fillna("Iné")
    df_parc["cpa"] = df_parc["cpa"].apply(cpa_display)
    df_parc = (df_parc.rename(columns={"cpa": "Parcela KN",
                                        "kultura_na": "LPIS kultúra",
                                        "ha": "Výmera (ha)"})
               [["Parcela KN", "KN druh pozemku", "LPIS kultúra", "Výmera (ha)"]]
               .sort_values("Výmera (ha)", ascending=False)
               .head(25))
    if not df_parc.empty:
        render_table(df_parc, badge_col="LPIS kultúra", badge_map=KULTURA_BADGE)
        st.write("")
        st.download_button("⬇️ Exportovať CSV",
            df_parc.to_csv(index=False).encode("utf-8"),
            "nesulady.csv", "text/csv")

# ── TAB: BPEJ ──────────────────────────────────────────────────────────────
with tab_bpej:
    st.subheader("Nevhodné využitie bonitovanej pôdy")
    st.caption("Parcely s produkčným potenciálom evidované v LPIS ako trvalý trávny porast.")

    df_ba = df_mf[
        df_mf["bpej"].notna() &
        df_mf["lpis_nazov"].str.lower().str.contains("trvalý trávny porast", na=False) &
        (df_mf["vymera_gis"] > 500)
    ].copy()
    df_ba = (df_ba.groupby(["parcela", "bpej"])
             .agg(vymera_gis=("vymera_gis", "max"))
             .reset_index())
    df_ba["Výmera (ha)"] = (df_ba["vymera_gis"] / 10000).round(2)
    df_ba["bpej"] = df_ba["bpej"].astype(int).astype(str)
    df_ba = (df_ba.rename(columns={"parcela": "Parcela KN", "bpej": "Kód BPEJ"})
             [["Parcela KN", "Kód BPEJ", "Výmera (ha)"]]
             .sort_values("Výmera (ha)", ascending=False)
             .head(50))

    if df_ba.empty:
        st.info("Žiadne záznamy pre zvolené kritériá.")
    else:
        k1, k2 = st.columns(2)
        k1.metric("Dotknutých parciel", len(df_ba))
        k2.metric("Celková plocha", f"{df_ba['Výmera (ha)'].sum():.1f} ha")
        st.divider()
        render_table(df_ba)

st.divider()
st.caption("Zelený kataster · Diplomová práca · k.ú. Zuberec · QGIS 3 + PostgreSQL/PostGIS 3 + Streamlit")
