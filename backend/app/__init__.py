"""
MiroFish Backend - Flask Anwendungsfabrik
"""

import os
import warnings

# Unterdrücke Warnungen des multiprocessing resource_tracker (aus Drittanbieterbibliotheken wie transformers)
# Muss vor allen anderen Imports gesetzt werden
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask-Anwendungsfabrik-Funktion"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Setze JSON-Kodierung: Stelle sicher, dass Chinesisch direkt angezeigt wird (anstatt \uXXXX-Format)
    # Flask >= 2.3 nutzt app.json.ensure_ascii, alte Versionen JSON_AS_ASCII-Konfiguration
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Setze Logging
    logger = setup_logger('mirofish')
    
    # Drucke nur im reloader-Subprozess Startinformationen (vermeide Drucken zweimal in Debug-Modus)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend wird gestartet...")
        logger.info("=" * 50)
    
    # Aktiviere CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Registriere Simulationsprozess-Cleanup-Funktion (stelle sicher, dass alle Simulationsprozesse beendet werden, wenn der Server geschlossen wird)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Registrierte Simulationsprozessbereinigungsfunktion")
    
    # Anfrage-Logging-Middleware
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"Anfrage: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"Request-Body: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Antwort: {response.status_code}")
        return response
    
    # Registriere Blaupause
    from .api import graph_bp, simulation_bp, report_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    
    # Healthcheck
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}
    
    if should_log_startup:
        logger.info("MiroFish Backend gestartet")
    
    return app

