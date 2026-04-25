"""Refined terminal styling — typography, cards, badges, sparklines."""
import streamlit as st

# ---------- Color system ----------
COLORS = {
    "bg":            "#0a0e17",
    "bg_elevated":   "#10151f",
    "bg_card":       "#141a26",
    "border":        "#1f2a3d",
    "border_strong": "#2a3651",
    "text":          "#e4e8f0",
    "text_dim":      "#8892a6",
    "text_muted":    "#5a6580",
    "gain":          "#00d4aa",
    "gain_soft":     "rgba(0,212,170,0.12)",
    "loss":          "#ff5c7a",
    "loss_soft":     "rgba(255,92,122,0.12)",
    "warn":          "#ffb74d",
    "warn_soft":     "rgba(255,183,77,0.12)",
    "accent":        "#4da6ff",
    "accent_soft":   "rgba(77,166,255,0.12)",
    "purple":        "#b388ff",
}

# Plotly reusable layout — apply via fig.update_layout(**PLOTLY_DARK_LAYOUT)
PLOTLY_DARK_LAYOUT = dict(
    paper_bgcolor=COLORS["bg_card"],
    plot_bgcolor=COLORS["bg_card"],
    font=dict(
        color=COLORS["text"],
        family="'JetBrains Mono', 'SF Mono', Menlo, monospace",
        size=11,
    ),
    margin=dict(l=30, r=20, t=50, b=30),
    xaxis=dict(
        gridcolor=COLORS["border"],
        zerolinecolor=COLORS["border"],
        tickfont=dict(size=10, color=COLORS["text_dim"]),
    ),
    yaxis=dict(
        gridcolor=COLORS["border"],
        zerolinecolor=COLORS["border"],
        tickfont=dict(size=10, color=COLORS["text_dim"]),
    ),
    hoverlabel=dict(
        bgcolor=COLORS["bg_elevated"],
        bordercolor=COLORS["border_strong"],
        font=dict(family="'JetBrains Mono', monospace", size=11),
    ),
)

BRAND_COLORS = [
    "#00d4aa", "#4da6ff", "#ffb74d", "#ff7eb6", "#b388ff",
    "#ff5c7a", "#7cdb9a", "#f5e663", "#62d6e8", "#ff9e7d",
]


def apply_custom_css() -> None:
    """Inject refined terminal-style CSS into the Streamlit app."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

        <style>
        /* ---------- Variables ---------- */
        :root {
            --bg: #0a0e17;
            --bg-elevated: #10151f;
            --bg-card: #141a26;
            --border: #1f2a3d;
            --border-strong: #2a3651;
            --text: #e4e8f0;
            --text-dim: #8892a6;
            --text-muted: #5a6580;
            --gain: #00d4aa;
            --loss: #ff5c7a;
            --warn: #ffb74d;
            --accent: #4da6ff;
            --font-mono: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-serif: 'Instrument Serif', Georgia, serif;
        }

        /* ---------- Global ---------- */
        html, body, [data-testid="stAppViewContainer"] {
            font-family: var(--font-sans);
            background-color: var(--bg);
            color: var(--text);
        }
        .main {
            background-color: var(--bg);
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 100% !important;
        }

        /* ---------- Typography ---------- */
        h1 {
            font-family: var(--font-serif);
            font-weight: 400;
            font-size: 2.4rem;
            letter-spacing: -0.01em;
            color: var(--text);
            border: none;
            padding: 0;
            margin-bottom: 0.5rem;
        }
        h2 {
            font-family: var(--font-sans);
            font-weight: 600;
            font-size: 1.15rem;
            letter-spacing: -0.005em;
            color: var(--text);
            border-bottom: 1px solid var(--border);
            padding-bottom: 6px;
            margin-top: 1.5rem !important;
            margin-bottom: 0.8rem !important;
        }
        h3 {
            font-family: var(--font-sans);
            font-weight: 600;
            font-size: 0.78rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--text-dim);
            border: none;
            padding: 0;
            margin-top: 1.8rem !important;
            margin-bottom: 0.6rem !important;
        }

        /* Numbers everywhere get monospace */
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"],
        [data-testid="stDataFrame"] {
            font-family: var(--font-mono) !important;
            font-variant-numeric: tabular-nums;
        }

        /* ---------- Metric cards ---------- */
        [data-testid="stMetric"] {
            background: linear-gradient(180deg, var(--bg-card) 0%, #11161f 100%);
            padding: 14px 18px;
            border-radius: 10px;
            border: 1px solid var(--border);
            transition: border-color 0.2s ease, transform 0.2s ease;
        }
        [data-testid="stMetric"]:hover {
            border-color: var(--border-strong);
        }
        [data-testid="stMetricLabel"] {
            color: var(--text-muted) !important;
            font-family: var(--font-sans) !important;
            font-size: 0.70rem !important;
            text-transform: uppercase;
            letter-spacing: 0.10em;
            font-weight: 600;
        }
        [data-testid="stMetricValue"] {
            color: var(--text) !important;
            font-size: 1.65rem !important;
            font-weight: 500;
            letter-spacing: -0.01em;
        }
        [data-testid="stMetricDelta"] {
            font-size: 0.85rem !important;
            font-weight: 500;
        }

        /* ---------- DataFrame ---------- */
        [data-testid="stDataFrame"] {
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
        }
        [data-testid="stDataFrame"] td {
            font-family: var(--font-mono) !important;
            font-size: 0.82rem !important;
        }

        /* ---------- Sidebar ---------- */
        [data-testid="stSidebar"] {
            background-color: #06090f;
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: var(--gain);
            border: none;
            font-family: var(--font-serif);
            font-weight: 400;
            letter-spacing: 0;
            text-transform: none;
        }

        /* ---------- Tabs ---------- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            background-color: var(--bg-elevated);
            border-radius: 8px;
            padding: 4px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: transparent;
            color: var(--text-dim);
            border-radius: 6px;
            padding: 8px 14px;
            font-family: var(--font-sans);
            font-size: 0.82rem;
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--bg-card) !important;
            color: var(--gain) !important;
        }

        /* ---------- Buttons ---------- */
        .stButton > button {
            background-color: var(--bg-elevated);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 8px;
            font-family: var(--font-sans);
            font-weight: 500;
        }
        .stButton > button:hover {
            background-color: var(--bg-card);
            border-color: var(--border-strong);
            color: var(--gain);
        }
        .stButton > button[kind="primary"] {
            background-color: var(--gain);
            color: #001a13;
            border: none;
            font-weight: 600;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #00b694;
            color: #001a13;
        }

        /* ---------- Inputs ---------- */
        [data-baseweb="input"], [data-baseweb="select"] {
            background-color: var(--bg-card) !important;
            border-color: var(--border) !important;
        }

        /* ---------- Hide Streamlit chrome ---------- */
        #MainMenu, footer, header {visibility: hidden; height: 0;}

        /* ---------- Custom classes ---------- */
        .hero-number {
            font-family: var(--font-serif);
            font-size: 3.2rem;
            font-weight: 400;
            letter-spacing: -0.02em;
            line-height: 1;
        }
        .hero-label {
            font-family: var(--font-sans);
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }

        .gain-text { color: var(--gain); }
        .loss-text { color: var(--loss); }
        .warn-text { color: var(--warn); }
        .dim-text  { color: var(--text-dim); }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: var(--font-sans);
            font-size: 0.70rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .badge-etf    { background: rgba(77,166,255,0.15); color: #4da6ff; }
        .badge-core   { background: rgba(0,212,170,0.15); color: #00d4aa; }
        .badge-tatica { background: rgba(179,136,255,0.15); color: #b388ff; }

        .badge-zona-compra { background: rgba(0,212,170,0.15); color: #00d4aa; }
        .badge-monitorizar { background: rgba(255,183,77,0.15); color: #ffb74d; }
        .badge-ja-correu   { background: rgba(255,183,77,0.20); color: #ffb74d; }
        .badge-abaixo-entry { background: rgba(77,166,255,0.15); color: #4da6ff; }
        .badge-stop-hit    { background: rgba(255,92,122,0.18); color: #ff5c7a; }

        /* Card wrapper */
        .tcard {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero_metric(label: str, value: str, delta: str | None = None, delta_positive: bool = True) -> str:
    """Return HTML for a big editorial-style hero number."""
    delta_html = ""
    if delta is not None:
        cls = "gain-text" if delta_positive else "loss-text"
        delta_html = f'<div style="font-family: var(--font-mono); font-size:1rem; margin-top:4px;" class="{cls}">{delta}</div>'
    return (
        f'<div class="hero-label">{label}</div>'
        f'<div class="hero-number" style="font-family: var(--font-mono);">{value}</div>'
        f"{delta_html}"
    )


def class_badge(classification: str) -> str:
    """HTML badge for position classification."""
    mapping = {"ETF": "etf", "Core": "core", "Tática": "tatica"}
    cls = mapping.get(classification, "core")
    return f'<span class="badge badge-{cls}">{classification}</span>'


def signal_badge(signal: str) -> str:
    """HTML badge for watchlist signal."""
    mapping = {
        "Zona de compra": "zona-compra",
        "Monitorizar": "monitorizar",
        "Já correu": "ja-correu",
        "Abaixo entry": "abaixo-entry",
        "Stop atingido": "stop-hit",
    }
    cls = mapping.get(signal, "monitorizar")
    return f'<span class="badge badge-{cls}">{signal}</span>'
