"""Palette for the window. No widgets and no network.

Navy and amber follow the icon. Text colors are chosen so body text stays
readable on the dark panels (contrast at least 4.5:1).
"""

from __future__ import annotations

NAVY = "#0E2433"
NAVY_DEEP = "#0A1B28"
PANEL = "#122A3C"
CARD = "#173447"
CARD_RAISED = "#1E4258"
CREAM = "#F7F4EF"
MUTED = "#C9D6E0"
AMBER = "#E6A317"
AMBER_HOT = "#F0C14A"
INK = "#0E2433"
LINE = "#2C5168"
ALTO = "#FF9B93"
MEDIO = "#F0C14A"
INFO = "#8ED4E2"
OK = "#7DDBA4"
OK_BG = "#14352A"
ERROR_BG = "#3A2428"

# Model 6 gauge. Body text on these panels stays at or above 4.5:1.
GAUGE_BG = "#10151C"
GAUGE_CARD = "#1B232E"
GAUGE_TRACK = "#2A3441"
GAUGE_LINE = "#3A4654"
GAUGE_CREAM = "#F4F1EA"
GAUGE_MUTED = "#B7C0C8"
GAUGE_INFO = "#7FD3E0"
GAUGE_MEDIO = "#F0C14A"
GAUGE_ALTO = "#FF6B6B"
GAUGE_ALTO_TEXT = "#FF8F87"
GAUGE_INK = "#1A1406"

UI_FONTS = ("Segoe UI", "Inter", "Cantarell", "DejaVu Sans")
MONO_FONTS = ("Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono", "DejaVu Sans Mono")


def _channel(value: int) -> float:
    scaled = value / 255
    if scaled <= 0.04045:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """WCAG relative luminance for a #RRGGBB color."""
    hex_color = color.removeprefix("#")
    red = int(hex_color[0:2], 16)
    green = int(hex_color[2:4], 16)
    blue = int(hex_color[4:6], 16)
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio. 4.5 is the usual floor for body text."""
    lighter = max(relative_luminance(foreground), relative_luminance(background))
    darker = min(relative_luminance(foreground), relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)
