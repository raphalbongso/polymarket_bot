"""
Polymarket Bot — Windows Desktop App

Opent het dashboard als een eigen Windows-programma (geen browser nodig).
Gebruikt pywebview voor een native venster.

Dubbelklik op start_app.bat om te starten, of:
    python app/desktop_app.py
"""
import sys
import os
import threading
import time
from pathlib import Path

# Voeg project root toe aan path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

DASHBOARD_PORT = 8050
APP_TITLE = "Polymarket Bot"
APP_WIDTH = 1400
APP_HEIGHT = 900


def start_server():
    """Start de dashboard server op de achtergrond."""
    from app.dashboard_server import DashboardHandler
    from http.server import HTTPServer

    server = HTTPServer(('127.0.0.1', DASHBOARD_PORT), DashboardHandler)
    server.serve_forever()


def open_native_window():
    """Open het dashboard in een native Windows venster."""
    try:
        import webview
        print(f'  App opent als native venster...')
        webview.create_window(
            APP_TITLE,
            f'http://127.0.0.1:{DASHBOARD_PORT}',
            width=APP_WIDTH,
            height=APP_HEIGHT,
            min_size=(800, 600),
            resizable=True,
            text_select=True,
        )
        webview.start()
    except ImportError:
        # pywebview niet geïnstalleerd → open in standaard browser
        print(f'  pywebview niet gevonden, opent in je browser...')
        print(f'  (Installeer pywebview voor een native app: pip install pywebview)')
        import webbrowser
        time.sleep(1)
        webbrowser.open(f'http://127.0.0.1:{DASHBOARD_PORT}')
        print(f'\n  Dashboard draait op http://localhost:{DASHBOARD_PORT}')
        print(f'  Druk Ctrl+C om te stoppen.\n')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


def main():
    # Force UTF-8 output on Windows
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print()
    print('  ========================================')
    print('    POLYMARKET BOT - Dashboard')
    print('  ========================================')
    print()

    # Start server op achtergrond
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # Open het venster
    open_native_window()


if __name__ == '__main__':
    main()
