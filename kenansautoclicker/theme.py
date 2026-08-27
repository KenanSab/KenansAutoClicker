"""Colour palettes and shared UI constants."""

APP_NAME = "Kenan's AutoClicker"
UI_FONT = "Segoe UI"          # falls back gracefully on macOS / Linux
TOUCHPAD_SPEED = 6            # pixels per unit of precision-trackpad delta


THEMES = {
    "dark": {
        "bg": "#0b0d13", "surface": "#141821", "surface2": "#1c2130", "raised": "#232a3b",
        "border": "#262c3b", "text": "#eef1f7", "muted": "#8b95a7", "faint": "#5d6779",
        "accent": "#6b8afd", "accent_soft": "#1e2740", "accent_fg": "#ffffff",
        "success": "#34d399", "danger": "#f87171", "field": "#0f131b",
        "track": "#2b3246",
        "warn_bg": "#2a1e13", "warn_fg": "#f5b567", "warn_border": "#4a3520",
        "search_bg": "#0f131b",
    },
    "light": {
        "bg": "#f5f7fb", "surface": "#ffffff", "surface2": "#f1f3f9", "raised": "#e8ecf5",
        "border": "#e2e6ef", "text": "#131722", "muted": "#6b7280", "faint": "#9aa3b2",
        "accent": "#4f6ef7", "accent_soft": "#e8edff", "accent_fg": "#ffffff",
        "success": "#059669", "danger": "#dc2626", "field": "#f8fafc",
        "track": "#d3d9e6",
        "warn_bg": "#fff5e6", "warn_fg": "#b45309", "warn_border": "#f5d9ac",
        "search_bg": "#f8fafc",
    },
}
