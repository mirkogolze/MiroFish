"""
Einstiegspunkt für den MiroFish Backend-Start
"""

import os
import sys

# Löse das Problem der chinesischen Zeichensalat in der Windows-Konsole durch Festlegung des UTF-8-Codes auf allen Imports vorher.
if sys.platform == 'win32':
    # Setzen Sie die Umgebungsvariablen, um sicherzustellen, dass Python UTF-8 verwendet.
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # Konfiguriere die Standardausgabe neu auf UTF-8.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Füge das Wurzelverzeichnis des Projekts dem Pfad hinzu.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """Hauptfunktion"""
    # Konfiguration überprüfen
    errors = Config.validate()
    if errors:
        print("Konfigurationsfehler: ")
        for err in errors:
            print(f"  - {err}")
        print("\nBitte überprüfen Sie die Konfiguration im .env-Datei.")
        sys.exit(1)
    
    # Erstelle Anwendung
    app = create_app()
    
    # Erhalte die Laufkonfiguration
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG
    
    # Starte den Dienst
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()

