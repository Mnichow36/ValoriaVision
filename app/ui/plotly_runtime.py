from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl

try:
    import plotly.io as pio
    PLOTLY_IO_AVAILABLE = True
except Exception:
    pio = None
    PLOTLY_IO_AVAILABLE = False


ROOT_DIR = Path(__file__).resolve().parents[2]
PLOTLY_CACHE_DIR = ROOT_DIR / "data" / "runtime"
PLOTLY_JS_PATH = PLOTLY_CACHE_DIR / "plotly.min.js"


def ensure_local_plotly_js() -> Path | None:
    """Materialize Plotly.js once as a local asset.

    The earlier versions loaded Plotly through the CDN for every chart.
    That causes a visible delay, especially on slower machines or without a
    warm browser cache. V0.6.6 writes the Plotly bundle locally once and all
    QWebEngineView charts reuse it.
    """

    if not PLOTLY_IO_AVAILABLE:
        return None
    try:
        if PLOTLY_JS_PATH.exists() and PLOTLY_JS_PATH.stat().st_size > 1_000_000:
            return PLOTLY_JS_PATH
        PLOTLY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        PLOTLY_JS_PATH.write_text(pio.get_plotlyjs(), encoding="utf-8")
        return PLOTLY_JS_PATH
    except Exception:
        return None


def build_plotly_html(fig, div_id: str, chart_height: int, extra_js: str = "", config: dict | None = None) -> tuple[str, QUrl | None]:
    """Build an HTML page for QWebEngineView using local Plotly when possible."""

    config = config or {
        "displayModeBar": False,
        "responsive": True,
        "locale": "fr",
        "scrollZoom": False,
    }
    local_js = ensure_local_plotly_js()
    include_plotlyjs = False if local_js else "cdn"
    body = fig.to_html(
        include_plotlyjs=include_plotlyjs,
        full_html=False,
        div_id=div_id,
        config=config,
    )
    script_tag = '<script src="plotly.min.js"></script>' if local_js else ""
    base_url = QUrl.fromLocalFile(str(local_js.parent) + "/") if local_js else None

    html = f"""
    <html>
    <head>
        <meta charset="utf-8" />
        {script_tag}
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: {chart_height}px;
                background: #FFFFFF;
                overflow: hidden;
            }}
            #{div_id}, .plotly-graph-div {{
                width: 100% !important;
                height: {chart_height}px !important;
            }}
        </style>
    </head>
    <body>{body}{extra_js}</body>
    </html>
    """
    return html, base_url
