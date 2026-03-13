COLORS = {
    "background": "#0f172a",
    "panel": "#1e293b",
    "accent": "#22c55e",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
}


def build_stylesheet() -> str:
    return f"""
    QWidget {{
        background-color: {COLORS['background']};
        color: {COLORS['text']};
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 12px;
    }}
    QFrame#panel {{
        background-color: {COLORS['panel']};
        border-radius: 12px;
        border: 1px solid #334155;
    }}
    QLineEdit, QTextEdit, QListWidget {{
        background-color: #111827;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 8px;
    }}
    QPushButton {{
        background-color: {COLORS['accent']};
        color: #052e16;
        border: none;
        border-radius: 8px;
        padding: 10px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: #4ade80;
    }}
    QPushButton:disabled {{
        background-color: #14532d;
        color: #86efac;
    }}
    QProgressBar {{
        background-color: #0b1220;
        border: 1px solid #334155;
        border-radius: 8px;
        text-align: center;
        min-height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: {COLORS['accent']};
        border-radius: 6px;
    }}
    QLabel#title {{
        font-size: 24px;
        font-weight: 700;
    }}
    QLabel#subtitle {{
        color: {COLORS['muted']};
    }}
    """
