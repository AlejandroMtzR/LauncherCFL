# -*- coding: utf-8 -*-
"""
Paleta y estilo central del launcher.

👉 Cambia un color aquí y se actualiza en TODO el launcher.
   (gris / azul / negro con acento naranja — tomado de la captura)
"""

# ── Superficies ────────────────────────────────────────────────
BG        = "#0a0e14"   # fondo base de la ventana
SURFACE   = "#0c1117"   # barra lateral / topbar / paneles oscuros
CARD      = "#12161f"   # tarjetas y paneles
CARD_HI   = "#161b26"   # tarjeta en hover / elevada
BORDER    = "rgba(255,255,255,0.06)"
BORDER_HI = "rgba(255,255,255,0.12)"

# ── Texto ──────────────────────────────────────────────────────
TEXT   = "#d8dee4"   # títulos / texto brillante
TEXT2  = "#aab2bd"   # cuerpo
MUTED  = "#7d8590"   # secundario
DIM    = "#515a66"   # muy tenue (footer, deshabilitado)

# ── Acento (naranja, como en la captura) ───────────────────────
ACCENT     = "#f97316"
ACCENT_HI  = "#fb923c"
ACCENT_LO  = "#c2410c"
ACCENT_RGB = (249, 115, 22)

# ── Estados ────────────────────────────────────────────────────
OK    = "#4ade80"
INFO  = "#38bdf8"
INFO2 = "#22d3ee"
WARN  = "#fbbf24"
ERROR = "#f87171"

# ── Colores de las categorías de mods (de la captura) ──────────
CATEGORIES = {
    "rpg":    "#a78bfa",   # RPG y Jefes        (violeta)
    "explor": "#34d399",   # Exploración        (esmeralda)
    "surviv": "#4f9ee6",   # Supervivencia      (azul cielo)
    "tech":   "#9b6cf0",   # Tecnología         (púrpura)
    "build":  "#f5a623",   # Construcción/Deco  (ámbar)
    "default": ACCENT,
}

# ── Tipografía ─────────────────────────────────────────────────
FONT      = "Segoe UI"
FONT_MONO = "Cascadia Code"


# ── Helpers ────────────────────────────────────────────────────
def rgb(hex_color):
    """'#rrggbb' -> (r, g, b)"""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgba(hex_color, a):
    """'#rrggbb', alpha(0..1) -> 'rgba(r,g,b,a)'  (para stylesheets)"""
    r, g, b = rgb(hex_color)
    return f"rgba({r},{g},{b},{a})"
