"""Styling, chart builders, and SHAP helpers for the dashboard. Kept out of app.py so no
single block there exceeds ~15 lines."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

CATEGORY_BANDS = [(0, 20, "Good"), (20, 40, "Fair"), (40, 60, "Moderate"), (60, 80, "Poor"), (80, 101, "Very Poor")]
CATEGORY_COLORS = {
    "Good": "#22C55E",
    "Fair": "#EAB308",
    "Moderate": "#F97316",
    "Poor": "#EF4444",
    "Very Poor": "#A855F7",
}
CATEGORY_TEXT_COLORS = {
    "Good": "#06210F",
    "Fair": "#241C02",
    "Moderate": "#2B1200",
    "Poor": "#FFFFFF",
    "Very Poor": "#FFFFFF",
}
ACCENT = "#38BDF8"
PANEL_BG = "#131A21"
TEXT = "#E7ECF2"
MUTED = "#8B96A5"
ALERT_THRESHOLD = 60  # "Poor" and worse
AQI_AXIS_LABEL = "Air Quality Index (EU scale)"

FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    # Weight *ranges* (not a fixed list) so every weight Streamlit's own heading/widget
    # CSS asks for gets a real loaded face instead of a browser-faked (synthesized) one,
    # which is what caused the doubled/ghosted-looking glyphs on the title.
    "family=Manrope:wght@400..800&family=JetBrains+Mono:wght@400..700&display=swap\">"
)


def categorize(value: float) -> str:
    for lo, hi, label in CATEGORY_BANDS:
        if value < hi:
            return label
    return "Very Poor"


def _rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def inject_css() -> str:
    # <link> tags (not @import) so the fonts load reliably regardless of how Streamlit
    # scopes injected <style> blocks; !important wins over Streamlit's own base CSS.
    return FONT_LINKS + f"""

<style>
/* :not(stIconMaterial) spares Streamlit's own icon glyphs (expander chevron, heading
   anchor icon, etc.), which are ligature text rendered through the "Material Symbols
   Rounded" icon font - forcing Manrope onto them made the raw ligature name ("expand_more"
   etc.) show up as literal text instead of an icon. */
[data-testid="stAppViewContainer"] *:not([data-testid="stIconMaterial"]) {{
    font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-synthesis: none;
}}
[data-testid="stIconMaterial"] {{
    font-family: "Material Symbols Rounded" !important;
}}
.block-container {{ padding-top: 2.2rem; max-width: 1200px; }}

@keyframes fadeSlideIn {{
    from {{ opacity: 0; transform: translateY(14px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes anchorPulse {{
    0% {{ box-shadow: 0 0 0 var(--glow-soft, transparent), 0 0 0 1px transparent; }}
    55% {{ box-shadow: 0 0 64px var(--glow-strong, transparent), 0 0 0 1px var(--glow-strong, transparent); }}
    100% {{ box-shadow: 0 0 46px var(--glow-strong, transparent), 0 0 0 1px var(--glow-soft, transparent); }}
}}

.stat-card {{
    background: {PANEL_BG};
    border: 1px solid rgba(255,255,255,0.06);
    border-left: 4px solid var(--cat-color, transparent);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 0 20px var(--glow-soft, transparent);
    animation: fadeSlideIn 0.6s cubic-bezier(.16,1,.3,1) both;
    transition: transform 220ms cubic-bezier(.16,1,.3,1), box-shadow 220ms ease, border-color 220ms ease;
}}
.stat-card:hover {{
    transform: translateY(-7px) scale(1.015);
    border-color: rgba(255,255,255,0.24);
    box-shadow: 0 0 36px var(--glow-strong, transparent);
}}
.anchor-card {{
    border-left-width: 6px;
    padding: 1.6rem 1.8rem;
    box-shadow: 0 0 46px var(--glow-strong, transparent), 0 0 0 1px var(--glow-soft, transparent);
    animation: fadeSlideIn 0.6s cubic-bezier(.16,1,.3,1) both, anchorPulse 1.2s cubic-bezier(.16,1,.3,1) 0.2s both;
}}
.anchor-card:hover {{ transform: translateY(-7px) scale(1.01); }}
div[data-testid="column"]:nth-of-type(1) .stat-card {{ animation-delay: 0ms; }}
div[data-testid="column"]:nth-of-type(2) .stat-card {{ animation-delay: 90ms; }}
div[data-testid="column"]:nth-of-type(3) .stat-card {{ animation-delay: 180ms; }}
div[data-testid="column"]:nth-of-type(4) .stat-card {{ animation-delay: 270ms; }}

.stat-label {{ color: {MUTED}; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.4rem; }}
[data-testid="stAppViewContainer"] .stat-card .stat-value {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 2.1rem; font-weight: 700; color: {TEXT}; line-height: 1;
}}
.stat-value.anchor {{ font-size: 3.6rem; }}

.badge {{ display: inline-block; margin-top: 0.55rem; padding: 2px 11px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }}
.anchor-card .badge {{ font-size: 0.9rem; padding: 3px 15px; margin-top: 0.7rem; }}

.alert-banner {{
    background: linear-gradient(90deg, rgba(239,68,68,0.16), rgba(239,68,68,0.05));
    border-left: 4px solid #EF4444;
    border-radius: 10px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 1.2rem;
    color: {TEXT};
    animation: fadeSlideIn 0.4s cubic-bezier(.16,1,.3,1) both;
}}
.alert-banner b {{ color: #FCA5A5; }}

@media (prefers-reduced-motion: reduce) {{
    .stat-card, .anchor-card, .alert-banner {{ animation: none !important; transition: none !important; }}
    .stat-card:hover, .anchor-card:hover {{ transform: none !important; }}
}}
</style>
"""


def badge_html(label: str) -> str:
    bg = CATEGORY_COLORS.get(label, "#999999")
    fg = CATEGORY_TEXT_COLORS.get(label, "#06120C")
    return f'<span class="badge" style="background:{bg};color:{fg};">{label}</span>'


def stat_card_html(label: str, value: str, category: str, anchor: bool = False) -> str:
    color = CATEGORY_COLORS.get(category, MUTED)
    size_class = "anchor" if anchor else ""
    card_class = "stat-card anchor-card" if anchor else "stat-card"
    vars_style = f"--cat-color:{color}; --glow-soft:{_rgba(color, 0.22)}; --glow-strong:{_rgba(color, 0.45)};"
    return (
        f'<div class="{card_class}" style="{vars_style}"><div class="stat-label">{label}</div>'
        f'<div class="stat-value {size_class}">{value}</div>{badge_html(category)}</div>'
    )


def alert_banner_html(messages: list[str]) -> str:
    body = "<br/>".join(messages)
    return f'<div class="alert-banner"><b>Air quality alert</b><br/>{body}</div>'


def _dark_layout(height: int, yaxis_title: str | None = None, yaxis_range: tuple[float, float] | None = None) -> dict:
    yaxis = dict(gridcolor="rgba(255,255,255,0.06)", zeroline=False, title=yaxis_title)
    if yaxis_range is not None:
        yaxis["range"] = list(yaxis_range)
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="Manrope, sans-serif"),
        margin=dict(t=30, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zeroline=False),
        yaxis=yaxis,
    )


def _band_ceiling(*series: pd.Series) -> float:
    data_max = max(float(s.max()) for s in series if len(s))
    return max(100.0, data_max * 1.15)


def _add_category_bands(fig: go.Figure, y_max: float) -> None:
    """Crisp, non-overlapping fill per category plus a dotted line at each threshold, so
    the five zones read as clearly bounded steps rather than a blended gradient."""
    for lo, hi, label in CATEGORY_BANDS:
        if lo >= y_max:
            continue
        top = y_max if label == "Very Poor" else min(hi, y_max)
        fig.add_hrect(y0=lo, y1=top, fillcolor=CATEGORY_COLORS[label], opacity=0.18, line_width=0, layer="below")
    for threshold in (20, 40, 60, 80):
        if threshold <= y_max:
            fig.add_hline(y=threshold, line=dict(color="rgba(255,255,255,0.22)", width=1, dash="dot"), layer="below")


def build_forecast_chart(recent_history: pd.DataFrame, forecast: pd.DataFrame, current_category: str) -> go.Figure:
    y_max = _band_ceiling(recent_history["european_aqi"], forecast["predicted_aqi"])
    fig = go.Figure()
    _add_category_bands(fig, y_max)

    fig.add_trace(go.Scatter(
        x=recent_history["timestamp"], y=recent_history["european_aqi"],
        mode="lines", name="Observed", line=dict(color=ACCENT, width=2.5),
    ))

    connector = pd.concat([
        recent_history.iloc[[-1]][["timestamp", "european_aqi"]].rename(columns={"european_aqi": "predicted_aqi"}),
        forecast[["timestamp", "predicted_aqi"]],
    ])
    marker_colors = [CATEGORY_COLORS[current_category]] + [CATEGORY_COLORS[c] for c in forecast["aqi_category"]]
    fig.add_trace(go.Scatter(
        x=connector["timestamp"], y=connector["predicted_aqi"],
        mode="lines+markers", name="Forecast",
        line=dict(color="#F97316", width=2.5, dash="dash"),
        marker=dict(size=9, color=marker_colors, line=dict(width=1, color="#0B0F14")),
    ))
    fig.update_layout(**_dark_layout(height=420, yaxis_title=AQI_AXIS_LABEL, yaxis_range=(0, y_max)))
    return fig


def build_trend_chart(history: pd.DataFrame) -> go.Figure:
    y_max = _band_ceiling(history["european_aqi"])
    fig = go.Figure()
    _add_category_bands(fig, y_max)
    fig.add_trace(go.Scatter(
        x=history["timestamp"], y=history["european_aqi"], mode="lines", name="AQI",
        line=dict(color=ACCENT, width=2), fill="tozeroy", fillcolor="rgba(56,189,248,0.08)",
    ))
    fig.update_layout(**_dark_layout(height=260, yaxis_title=AQI_AXIS_LABEL, yaxis_range=(0, y_max)))
    fig.update_layout(showlegend=False)
    return fig


def compute_shap_contributions(model, scaler, feature_cols, background_df: pd.DataFrame, instance_row: pd.Series):
    """Returns per-feature SHAP values for one instance, or None if the model type isn't
    tree- or linear-based (e.g. a TensorFlow model). Runs every rerun regardless of
    whether the "Why this forecast" expander is open (Streamlit re-executes the whole
    script on every interaction), so it's timed here to catch it as a hidden cost."""
    import time

    import shap

    t0 = time.perf_counter()
    background = scaler.transform(background_df[feature_cols].dropna())
    if background.shape[0] > 100:
        background = shap.sample(background, 100, random_state=0)
    x_instance = scaler.transform(instance_row[feature_cols].to_frame().T)

    if hasattr(model, "estimators_"):
        explainer = shap.TreeExplainer(model)
        raw = explainer.shap_values(x_instance)
    elif hasattr(model, "coef_"):
        explainer = shap.LinearExplainer(model, background)
        raw = explainer.shap_values(x_instance)
    else:
        return None

    raw = np.asarray(raw)
    while raw.ndim > 2:
        raw = raw[0]
    print(f"[timing] compute_shap_contributions(): {time.perf_counter() - t0:.2f}s")
    return raw[0]


def build_shap_chart(values: np.ndarray, feature_cols: list[str], top_n: int = 8) -> go.Figure:
    order = np.argsort(np.abs(values))[::-1][:top_n]
    feats = [feature_cols[i] for i in order][::-1]
    vals = [values[i] for i in order][::-1]
    colors = ["#EF4444" if v > 0 else ACCENT for v in vals]
    fig = go.Figure(go.Bar(x=vals, y=feats, orientation="h", marker_color=colors))
    fig.update_layout(**_dark_layout(height=320))
    fig.update_layout(xaxis_title="Impact on predicted AQI", showlegend=False)
    return fig
