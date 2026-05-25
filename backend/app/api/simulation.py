"""
Simulationsbezogene API-Routinen
Schritt 2: Automatisches Lesen, Filtern von Zep-Entitäten und Vorbereitung sowie Durchführung der OASIS-Simulation (vollständig automatisiert)
"""

import os
import traceback
from flask import request, jsonify, send_file

from . import simulation_bp
from ..config import Config
from ..services.zep_entity_reader import ZepEntityReader
from ..services.oasis_profile_generator import OasisProfileGenerator
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale
from ..models.project import ProjectManager

logger = get_logger('mirofish.api.simulation')


# Interview Prompt Optimierungsvorsatz
# Hinzufügen dieses Vorsatzes kann verhindern, dass Agent Werkzeuge aufruft und stattdessen direkt mit Text antwortet
INTERVIEW_PROMPT_PREFIX = "Verwende Text, um direkt zu antworten:"


def optimize_interview_prompt(prompt: str) -> str:
    """
    Interview-Frage optimieren, Präfix hinzufügen um Tool-Aufrufe durch den Agent zu vermeiden
    
    Args:
        prompt: Ursprüngliche Frage
        
    Returns:
        Optimierte Frage
    """
    if not prompt:
        return prompt
    # Verhindere doppelte Hinzufügung des Vorsatzes
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


# ============== Entität-Lese-API ==============

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
	Hol alle Entitäten aus dem Graphen (bereits gefiltert)
	
	Nur Knoten, die den vordefinierten Entitätstypen entsprechen, werden zurückgegeben (Labels sind nicht nur Nodes von Entity).
	
	Query Parameter:
		entity_types: Liste der entitäts-typen, durch Kommas getrennt (optional, für zusätzliche Filterung)
		enrich: Soll Informations über die zugehörigen Kanten zurückgegeben werden? (Standardwert true)"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        logger.info(f"Graph-Entitäten abrufen: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}")
        
        reader = ZepEntityReader()
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Graph-Entitäten abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """Detaillierte Informationen für einzelnes Objekt abrufen"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        reader = ZepEntityReader()
        entity = reader.get_entity_with_context(graph_id, entity_uuid)
        
        if not entity:
            return jsonify({
                "success": False,
                "error": t('api.entityNotFound', id=entity_uuid)
            }), 404
        
        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Entitätsdetails abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Alle Objekte des angegebenen Typs abrufen"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        reader = ZepEntityReader()
        entities = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "count": len(entities),
                "entities": [e.to_dict() for e in entities]
            }
        })
        
    except Exception as e:
        logger.error(f"Entität abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation-Verwaltung-API ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """
    Neue Simulation erstellen
    
    Hinweis: Parameter wie max_rounds werden intelligent vom LLM generiert, keine manuelle Einstellung nötig
    
    Anfrage (JSON):
        {
            "project_id": "proj_xxxx",      // Pflicht
            "graph_id": "mirofish_xxxx",    // Optional, wird sonst aus dem Projekt abgerufen
            "enable_twitter": true,          // Optional, Standard true
            "enable_reddit": true            // Optional, Standard true
        }
    
    Rückgabe:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "project_id": "proj_xxxx",
                "graph_id": "mirofish_xxxx",
                "status": "created",
                "enable_twitter": true,
                "enable_reddit": true,
                "created_at": "2025-12-01T10:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": t('api.requireProjectId')
            }), 400
        
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=project_id)
            }), 404
        
        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.graphNotBuilt')
            }), 400
        
        manager = SimulationManager()
        state = manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
        )
        
        return jsonify({
            "success": True,
            "data": state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Simulation erstellen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _check_simulation_prepared(simulation_id: str) -> tuple:
    """
	Überprüfen, ob die Simulation bereits fertig vorbereitet ist
	
	Überprüfungsbedingungen:
	1. state.json existiert und der Status ist "ready"
	2. notwendige Dateien vorhanden: reddit_profiles.json, twitter_profiles.csv, simulation_config.json
	
	Hinweis: Die Ausführungsdateien (run_*.py) bleiben im Verzeichnis backend/scripts/, werden nicht mehr in das Simulationsverzeichnis kopiert.
	
	Parameter:
		simulation_id: ID der Simulation
	
	Rückgabewert:
		(is_prepared: bool, info: dict)
	"""
    import os
    from ..config import Config
    
    simulation_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
    
    # Prüfe, ob Verzeichnis existiert
    if not os.path.exists(simulation_dir):
        return False, {"reason": "Simulationsverzeichnis existiert nicht"}
    
    # Liste der notwendigen Dateien (ohne Skripte, die im backend/scripts/ Verzeichnis liegen)
    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv"
    ]
    
    # Prüfen, ob Datei existiert
    existing_files = []
    missing_files = []
    for f in required_files:
        file_path = os.path.join(simulation_dir, f)
        if os.path.exists(file_path):
            existing_files.append(f)
        else:
            missing_files.append(f)
    
    if missing_files:
        return False, {
            "reason": "Notwendige Dateien fehlen",
            "missing_files": missing_files,
            "existing_files": existing_files
        }
    
    # Überprüfe den Zustand in state.json
    state_file = os.path.join(simulation_dir, "state.json")
    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)
        
        # Detailierte Protokolldatei
        logger.debug(f"Simulationsvorbereitungsstatus prüfen: {simulation_id}, status={status}, config_generated={config_generated}")
        
        # Wenn config_generated=True und die Datei existiert, wird als fertig angesehen
        # Die folgenden Zustände deuten auf eine vollständige Vorbereitung hin:
        # - ready: Fertig vorbereitet, kann gestartet werden
        # - preparing: Wenn config_generated=True ist die Vorbereitung abgeschlossen
        # - running: In Ausführung, was bedeutet, dass die Vorbereitung schon lange vorher abgeschlossen war
        # - completed: Ausführung abgeschlossen, was bedeutet, dass die Vorbereitung schon lange vorher abgeschlossen war
        # - stopped: Angehalten, was bedeutet, dass die Vorbereitung schon lange vorher abgeschlossen war
        # - failed: Ausführung fehlgeschlagen (aber die Vorbereitung ist abgeschlossen)
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed"]
        if status in prepared_statuses and config_generated:
            # Hole Dateistatistik
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")
            config_file = os.path.join(simulation_dir, "simulation_config.json")
            
            profiles_count = 0
            if os.path.exists(profiles_file):
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0
            
            # Wenn der Zustand preparing ist, aber die Datei fertig ist, aktualisiere den Zustand automatisch auf ready
            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    from datetime import datetime
                    state_data["updated_at"] = datetime.now().isoformat()
                    with open(state_file, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Simulationsstatus automatisch aktualisieren: {simulation_id} preparing -> ready")
                    status = "ready"
                except Exception as e:
                    logger.warning(f"Automatische Statusaktualisierung fehlgeschlagen: {e}")
            
            logger.info(f"Simulation {simulation_id} Prüfergebnis: Vorbereitung abgeschlossen (status={status}, config_generated={config_generated})")
            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files
            }
        else:
            logger.warning(f"Simulation {simulation_id} Prüfergebnis: Vorbereitung nicht abgeschlossen (status={status}, config_generated={config_generated})")
            return False, {
                "reason": f"Status nicht in Vorbereitungsliste oder config_generated ist false: status={status}, config_generated={config_generated}",
                "status": status,
                "config_generated": config_generated
            }
            
    except Exception as e:
        return False, {"reason": f"Statusdatei lesen fehlgeschlagen: {str(e)}"}


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """
	Vorbereitung des Simulationsumfelds (asynchrone Aufgabe, LLM generiert alle Parameter intelligent)

	Dies ist eine zeitaufwändige Operation. Die Schnittstelle gibt sofort einen task_id zurück.
	Verwenden Sie GET /api/simulation/prepare/status zum Abfragen des Fortschritts.

	Funktionen:
	- Automatische Erkennung abgeschlossener Vorbereitungen, um doppelte Generierung zu vermeiden
	- Wenn bereits vorbereitet, wird direkt das vorhandene Ergebnis zurückgegeben
	- Unterstützung für erzwungene NeuGenerierung (force_regenerate=true)

	Schritte:
	1. Überprüfen, ob bereits abgeschlossene Vorbereitungen existieren
	2. Lesen und Filtern von Entitäten aus dem Zep-Grafikmodell
	3. Generieren eines OASIS Agent Profiles für jede Entität (mit Wiederholungsmechanismus)
	4. LLM generiert die Simulationskonfiguration intelligent (mit Wiederholungsmechanismus)
	5. Speichern der Konfigurationsdatei und des Vordefinierten Skripts

	Anfrage (JSON):
	{
		"simulation_id": "sim_xxxx",                   // Pflichtfeld, Simulations-ID
		"entity_types": ["Student", "PublicFigure"],  // Optional, spezifiziert die Entitätstypen
		"use_llm_for_profiles": true,                 // Optional, ob LLM zur Generierung von Personae verwendet wird
		"parallel_profile_count": 5,                  // Optional, Anzahl paralleler Profilegenerierungen, Standardwert ist 5
		"force_regenerate": false                     // Optional, erzwungene NeuGenerierung, Standardwert ist false
	}

	Antwort:
	{
		"success": true,
		"data": {
			"simulation_id": "sim_xxxx",
			"task_id": "task_xxxx",           // Wird zurückgegeben, wenn eine neue Aufgabe gestartet wird
			"status": "preparing|ready",
			"message": "Vorbereitungsaufgabe wurde gestartet|Es existiert bereits eine abgeschlossene Vorbereitung",
			"already_prepared": true|false    // Ob bereits vorbereitet
		}
	}"""
    import threading
    import os
    from ..models.task import TaskManager, TaskStatus
    from ..config import Config
    
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # Überprüfe, ob eine erzwungene NeuGenerierung erforderlich ist
        force_regenerate = data.get('force_regenerate', False)
        logger.info(f"/prepare-Anfrage verarbeiten: simulation_id={simulation_id}, force_regenerate={force_regenerate}")
        
        # Überprüfe, ob die Vorbereitung bereits abgeschlossen wurde (um doppelte Generierungen zu vermeiden)
        if not force_regenerate:
            logger.debug(f"Prüfe Simulation {simulation_id} Vorbereitungsstatus prüfen...")
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            logger.debug(f"Prüfergebnis: is_prepared={is_prepared}, prepare_info={prepare_info}")
            if is_prepared:
                logger.info(f"Simulation {simulation_id} bereits vorbereitet, überspringe doppelte Generierung")
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "message": t('api.alreadyPrepared'),
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
            else:
                logger.info(f"Simulation {simulation_id} nicht vorbereitet, starte Vorbereitungsaufgabe")
        
        # Hole notwendige Informationen aus dem Projekt
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        # Hole Simulationsanforderungen
        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.projectMissingRequirement')
            }), 400
        
        # Hole Dokumententext
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""
        
        entity_types_list = data.get('entity_types')
        use_llm_for_profiles = data.get('use_llm_for_profiles', True)
        parallel_profile_count = data.get('parallel_profile_count', 5)
        
        # ========== Synchronisiere die Anzahl der Entitäten (vor dem Start des Hintergrundauftrags) ==========
        # So kann das Frontend sofort nach Aufruf von prepare die erwartete Gesamtzahl der Agents abrufen
        try:
            logger.info(f"Entitätsanzahl synchron abrufen: graph_id={state.graph_id}")
            reader = ZepEntityReader()
            # Schnelle Entitätserfassung (keine Kanteninformationen, nur Anzahl)
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types_list,
                enrich_with_edges=False  # Keine Kanteninformationen abrufen, um die Geschwindigkeit zu erhöhen
            )
            # Speichere Entitätanzahl im Zustand (für sofortige Abrufbarkeit durch Frontend)
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(f"Erwartete Entitätsanzahl: {filtered_preview.filtered_count}, Typ: {filtered_preview.entity_types}")
        except Exception as e:
            logger.warning(f"Entitätsanzahl synchron abrufen fehlgeschlagen (Hintergrund-Wiederholung): {e}")
            # Fehlschläge beeinflussen den nachfolgenden Prozess nicht, der Hintergrundauftrag wird neu abgerufen
        
        # Erstelle asynchronen Task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id
            }
        )
        
        # Aktualisiere die Simulationsstatus (inklusive vorab abgerufenen Entitätanzahl)
        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # Definiere Hintergrundtask
        def run_prepare():
            set_locale(current_locale)
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message=t('progress.startPreparingEnv')
                )
                
                # Vorbereitung der Simulation (mit Fortschrittsrückmeldung)
                # Speichere Details des Fortschrittsstadiums
                stage_details = {}
                
                def progress_callback(stage, progress, message, **kwargs):
                    # Berechne Gesamtfortschritt
                    stage_weights = {
                        "reading": (0, 20),           # 0-20%
                        "generating_profiles": (20, 70),  # 20-70%
                        "generating_config": (70, 90),    # 70-90%
                        "copying_scripts": (90, 100)       # 90-100%
                    }
                    
                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)
                    
                    # Erstelle detaillierte Fortschrittsinformationen
                    stage_names = {
                        "reading": t('progress.readingGraphEntities'),
                        "generating_profiles": t('progress.generatingProfiles'),
                        "generating_config": t('progress.generatingSimConfig'),
                        "copying_scripts": t('progress.preparingScripts')
                    }
                    
                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)
                    
                    # Aktualisiere Stadiumsdetails
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", "")
                    }
                    
                    # Erstelle detaillierte Fortschrittsinformationen
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message
                    }
                    
                    # Erstelle kurze Nachrichten
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
                    
                    task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data
                    )
                
                result_state = manager.prepare_simulation(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types_list,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count
                )
                
                # Auftrag abgeschlossen
                task_manager.complete_task(
                    task_id,
                    result=result_state.to_simple_dict()
                )
                
            except Exception as e:
                logger.error(f"Simulationsvorbereitung fehlgeschlagen: {str(e)}")
                task_manager.fail_task(task_id, str(e))
                
                # Aktualisiere den Simulationsstatus auf fehlgeschlagen
                state = manager.get_simulation(simulation_id)
                if state:
                    state.status = SimulationStatus.FAILED
                    state.error = str(e)
                    manager._save_simulation_state(state)
        
        # Starte Hintergrundthread
        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": t('api.prepareStarted'),
                "already_prepared": False,
                "expected_entities_count": state.entities_count,  # Erwartete Gesamtzahl der Agents
                "entity_types": state.entity_types  # Liste der Entitätstypen
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Vorbereitungsaufgabe starten fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
	Abfrage des Vorbereitungsauftragsstatus
	
	Zwei Abfragemethoden werden unterstützt:
	1. Verwenden Sie task_id, um den Status eines laufenden Auftrags abzurufen.
	2. Verwenden Sie simulation_id, um zu überprüfen, ob bereits eine Vorbereitung abgeschlossen wurde.
	
	Anfrage (JSON):
		{
		    "task_id": "task_xxxx",          // optional, task_id aus der prepare-Antwort
		    "simulation_id": "sim_xxxx"      // optional, Simulation-ID zur Überprüfung abgeschlossener Vorbereitungen
		}
	
	Antwort:
		{
		    "success": true,
		    "data": {
		        "task_id": "task_xxxx",
		        "status": "processing|completed|ready",
		        "progress": 45,
		        "message": "...",
		        "already_prepared": true|false,  // ob bereits eine Vorbereitung abgeschlossen wurde
		        "prepare_info": {...}            // Details einer abgeschlossenen Vorbereitung
		    }
		}
	"""
    from ..models.task import TaskManager
    
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # Wenn ein simulation_id bereitgestellt wurde, überprüfe zuerst, ob die Vorbereitung abgeschlossen ist
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": t('api.alreadyPrepared'),
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
        
        # Ohne task_id wird eine Fehlermeldung zurückgegeben
        if not task_id:
            if simulation_id:
                # Es gibt ein simulation_id, aber die Vorbereitung ist noch nicht abgeschlossen
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": t('api.notStartedPrepare'),
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": t('api.requireTaskOrSimId')
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            # Auftrag existiert nicht, wenn jedoch ein simulation_id vorhanden ist, überprüfe, ob die Vorbereitung abgeschlossen ist
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": t('api.taskCompletedPrepared'),
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })
            
            return jsonify({
                "success": False,
                "error": t('api.taskNotFound', id=task_id)
            }), 404
        
        task_dict = task.to_dict()
        task_dict["already_prepared"] = False
        
        return jsonify({
            "success": True,
            "data": task_dict
        })
        
    except Exception as e:
        logger.error(f"Aufgabenstatus abfragen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """Simulationsstatus abrufen"""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        result = state.to_dict()
        
        # Füge Laufanweisungen hinzu, wenn die Simulation bereit ist
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Simulationsstatus abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
	Liste aller Simulationen
	
	Query-Parameter:
		project_id: Filtert nach Projekt-ID (optional)
	"""
    try:
        project_id = request.args.get('project_id')
        
        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)
        
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })
        
    except Exception as e:
        logger.error(f"Simulationen auflisten fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _get_report_id_for_simulation(simulation_id: str) -> str:
    """
	Erhalte den neuesten Report-ID für die Simulation.
	
	Iteriere über das Verzeichnis reports und finde den Report, dessen simulation_id übereinstimmt. Wenn mehrere Reports vorhanden sind, wird der jüngste (gemäß created_at sortiert) zurückgegeben.
	
	Args:
	    simulation_id: Simulations-ID
	    
	Returns:
	    report_id oder None
	"""
    import json
    from datetime import datetime
    
    # reports Verzeichnispfad: backend/uploads/reports
    # __file__ ist app/api/simulation.py, zwei Ordner höher bei backend/
    reports_dir = os.path.join(os.path.dirname(__file__), '../../uploads/reports')
    if not os.path.exists(reports_dir):
        return None
    
    matching_reports = []
    
    try:
        for report_folder in os.listdir(reports_dir):
            report_path = os.path.join(reports_dir, report_folder)
            if not os.path.isdir(report_path):
                continue
            
            meta_file = os.path.join(report_path, "meta.json")
            if not os.path.exists(meta_file):
                continue
            
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                if meta.get("simulation_id") == simulation_id:
                    matching_reports.append({
                        "report_id": meta.get("report_id"),
                        "created_at": meta.get("created_at", ""),
                        "status": meta.get("status", "")
                    })
            except Exception:
                continue
        
        if not matching_reports:
            return None
        
        # Sortiere nach Erstellungszeit in absteigender Reihenfolge und gib das neueste zurück
        matching_reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matching_reports[0].get("report_id")
        
    except Exception as e:
        logger.warning(f"Suche Simulation {simulation_id} Bericht fehlgeschlagen: {e}")
        return None


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    Holt die Liste der historischen Simulationsprojekte (mit Projektdetails)
    
    Wird für die Anzeige von historischen Projekten auf der Startseite verwendet. Gibt eine Liste von Simulationen zurück, die reichhaltige Informationen wie Projektname und Beschreibung enthalten.
    
    Query-Parameter:
        limit: Begrenzung der Rückgabe (Standardwert 20)
    
    Rückgabewert:
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "Wuhan University Sentiment Analysis",
                    "simulation_requirement": "If Wuhan University publishes...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v1.0.2"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        manager = SimulationManager()
        simulations = manager.list_simulations()[:limit]
        
        # Erhöhe die Simulationsdaten, lese nur aus der Simulation-Datei
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()
            
            # Lese die Simulationskonfiguration (simulation_requirement aus simulation_config.json)
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # Empfohlene Anzahl der Runden
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 / 
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0
            
            # Lese den Laufstatus (aktuelle Rundenanzahl aus run_state.json)
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # Verwende die von der Benutzerkonfiguration angegebene total_rounds, ansonsten empfohlene Anzahl
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds
            
            # Lese die Dateien der zugeordneten Projekte (maximal drei)
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {"filename": f.get("filename", "Unbekannte Datei")} 
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []
            
            # Lese den zugehörigen report_id (neuester Report für diese Simulation)
            sim_dict["report_id"] = _get_report_id_for_simulation(sim.simulation_id)
            
            # Füge Versionsnummer hinzu
            sim_dict["version"] = "v1.0.2"
            
            # Formate das Datum
            try:
                created_date = sim_dict.get("created_at", "")[:10]
                sim_dict["created_date"] = created_date
            except:
                sim_dict["created_date"] = ""
            
            enriched_simulations.append(sim_dict)
        
        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"Simulationsverlauf abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
	Abrufen des Agenten-Profiles der Simulation
	
	Query-Parameter:
		platform: Plattformtyp (reddit/twitter, Standardwert reddit)
	"""
    try:
        platform = request.args.get('platform', 'reddit')
        
        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Profil abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
	Echtzeit-Abruf des Agenten-Profiles der Simulation (zum Echtzeit-Betrachten während des Generierens)
	
	Unterschiede zum /profiles-Interface:
	- Direkter Dateizugriff, ohne SimulationManager zu verwenden
	- Geeignet für das Echtzeit-Betrachten während des Generierens
	- Rückgabe zusätzlicher Metadaten (z.B. letzte Änderungszeit der Datei, ob aktuell generiert wird usw.)
	
	Abfrageparameter:
		platform: Plattformtyp (reddit/twitter, Standard ist reddit)
	
	Rückgabewert:
		{
			"success": true,
			"data": {
				"simulation_id": "sim_xxxx",
				"platform": "reddit",
				"count": 15,
				"total_expected": 93, // Erwartete Gesamtzahl (falls vorhanden)
				"is_generating": true, // Generierung läuft
				"file_exists": true,
				"file_modified_at": "2025-12-04T18:20:00",
				"profiles": [...]
			}
		}"""
    import json
    import csv
    from datetime import datetime
    
    try:
        platform = request.args.get('platform', 'reddit')
        
        # Lese den Simulationsverzeichnispfad
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # Bestimme den Dateipfad
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")
        
        # Prüfen, ob Datei existiert
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None
        
        if file_exists:
            # Lese die Änderungszeit der Datei
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        profiles = list(reader)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Profiles-Datei lesen fehlgeschlagen (möglicherweise wird gerade geschrieben): {e}")
                profiles = []
        
        # Überprüfe, ob eine Erstellung läuft (state.json)
        is_generating = False
        total_expected = None
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
            except Exception:
                pass
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })
        
    except Exception as e:
        logger.error(f"Echtzeit-Profil abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
	Echtzeit-Abruf der Simulationskonfiguration (zum Echtzeit-Betrachten des Fortschritts während der Generierung)
	
	Unterschiede zum /config-Endpunkt:
	- Direkter Dateizugriff, ohne SimulationManager zu verwenden
	- Geeignet für das Echtzeit-Betrachten während der Generierung
	- Rückgabe zusätzlicher Metadaten (wie z.B. die letzte Änderungszeit der Datei oder ob sie gerade generiert wird)
	- Bereitstellung von Informationen, auch wenn die Konfiguration noch nicht vollständig generiert wurde
	
	Rückgabewert:
	{
		"success": true,
		"data": {
			"simulation_id": "sim_xxxx",
			"file_exists": true,
			"file_modified_at": "2025-12-04T18:20:00",
			"is_generating": true,  // Ist die Generierung im Gange?
			"generation_stage": "generating_config",  // Aktueller Generierungsstatus
			"config": {...}  // Konfigurationsinhalt (falls vorhanden)
		}
	}"""
    import json
    from datetime import datetime
    
    try:
        # Lese den Simulationsverzeichnispfad
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404
        
        # Konfiguriere den Dateipfad
        config_file = os.path.join(sim_dir, "simulation_config.json")
        
        # Prüfen, ob Datei existiert
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None
        
        if file_exists:
            # Lese die Änderungszeit der Datei
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Config-Datei lesen fehlgeschlagen (möglicherweise wird gerade geschrieben): {e}")
                config = None
        
        # Überprüfe, ob eine Erstellung läuft (state.json)
        is_generating = False
        generation_stage = None
        config_generated = False
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    config_generated = state_data.get("config_generated", False)
                    
                    # Überprüfe die aktuelle Phase
                    if is_generating:
                        if state_data.get("profiles_generated", False):
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif status == "ready":
                        generation_stage = "completed"
            except Exception:
                pass
        
        # Erstelle das Rückgabedatenobjekt
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "generation_stage": generation_stage,
            "config_generated": config_generated,
            "config": config
        }
        
        # Extrahiere einige wichtige Statistiken, wenn die Konfiguration existiert
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"Echtzeit-Config abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    Ruft die Simulationskonfiguration (vollständige Konfiguration, die intelligent von einem großen Sprachmodell generiert wurde) ab.
    
    Gibt zurück:
        - time_config: Zeit-Konfiguration (Simulationsdauer, Runden, Hoch-/Tiefpunkte)
        - agent_configs: Aktivitätskonfiguration für jeden Agenten (Aktivität, Sprechfrequenz, Positionierung usw.)
        - event_config: Ereignis-Konfiguration (Anfangsbeiträge, Hot-Topics)
        - platform_configs: Plattform-Konfiguration
        - generation_reasoning: Erklärung des Konfigurations-Raisonnement durch das große Sprachmodell"""
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)
        
        if not config:
            return jsonify({
                "success": False,
                "error": t('api.configNotFound')
            }), 404
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Konfiguration abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """Simulationskonfigurationsdatei herunterladen"""
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": t('api.configFileNotFound')
            }), 404
        
        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )
        
    except Exception as e:
        logger.error(f"Konfiguration herunterladen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    Simulations-Laufskript herunterladen (generisches Skript, unter backend/scripts/)
    
    Mögliche Werte für script_name:
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    try:
        # Skript im backend/scripts/ Verzeichnis
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        # Überprüfe den Skriptnamen
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py", 
            "run_parallel_simulation.py",
            "action_logger.py"
        ]
        
        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": t('api.unknownScript', name=script_name, allowed=allowed_scripts)
            }), 400
        
        script_path = os.path.join(scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": t('api.scriptFileNotFound', name=script_name)
            }), 404
        
        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )
        
    except Exception as e:
        logger.error(f"Skript herunterladen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Profilegenerierung (unabhängig) ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    OASIS Agent Profile direkt aus dem Graphen generieren (ohne Simulation zu erstellen)
    
    Anfrage (JSON):
        {
            "graph_id": "mirofish_xxxx",     // Pflicht
            "entity_types": ["Student"],      // Optional
            "use_llm": true,                  // Optional
            "platform": "reddit"              // Optional
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphId')
            }), 400
        
        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')
        
        reader = ZepEntityReader()
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )
        
        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": t('api.noMatchingEntities')
            }), 400
        
        generator = OasisProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )
        
        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })
        
    except Exception as e:
        logger.error(f"Profil generieren fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulationslaufsteuerung ==============

@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """
	Starte die Simulation ausführen.

	Anfrage (JSON):
	{
		"simulation_id": "sim_xxxx",          // Pflichtfeld, ID der Simulation
		"platform": "parallel",                // Optional: twitter / reddit / parallel (Standard)
		"max_rounds": 100,                     // Optional: Maximale Anzahl an Runden zur Kürzung langer Simulationslaufe
		"enable_graph_memory_update": false,   // Optional: Aktiviere die dynamische Aktualisierung des Agentenverhaltens in das Zep-Graph-Memory
		"force": false                         // Optional: Erzwinge eine erneute Startsequenz (stoppt laufende Simulation und löscht Logs)
	}

	Über den Parameter force:
	- Wenn aktiviert, wird die aktuell laufende oder abgeschlossene Simulation gestoppt und ihre Laufe-Logs gelöscht.
	- Gelöscht werden: run_state.json, actions.jsonl, simulation.log usw.
	- Konfigurationsdateien (simulation_config.json) und Profildateien bleiben erhalten.
	- Dies ist nützlich für Szenarien, in denen eine erneute Ausführung der Simulation erforderlich ist.

	Über den Parameter enable_graph_memory_update:
	- Wenn aktiviert, werden alle Aktivitäten aller Agenten (Beiträge, Kommentare, Likes usw.) in Echtzeit aktualisiert in das Zep-Graph-Memory.
	- Dies ermöglicht es dem Graph zu "erinnern" an den Simulationsprozess für zukünftige Analysen oder AI-Dialoge.
	- Es ist erforderlich, dass Projekte mit der Simulation einen gültigen graph_id haben.
	- Ein Batch-Aktualisierungssystem wird verwendet um die Anzahl API-Anfragen zu minimieren.

	Rückgabe:
	{
		"success": true,
		"data": {
			"simulation_id": "sim_xxxx",
			"runner_status": "running",
			"process_pid": 12345,
			"twitter_running": true,
			"reddit_running": true,
			"started_at": "2025-12-01T10:00:00",
			"graph_memory_update_enabled": true,  // Ist die Aktualisierung des Graph-Memories aktiviert?
			"force_restarted": true               // Wurde es durch eine erzwungene Neustart ausgelöst?
		}
	}
	"""
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        platform = data.get('platform', 'parallel')
        max_rounds = data.get('max_rounds')  # Optional: Maximale Anzahl der Simulationen
        enable_graph_memory_update = data.get('enable_graph_memory_update', False)  # Optional: Aktiviere das Updaten des Graphen-Verweises
        force = data.get('force', False)  # Optional: Erzwinge den Neustart

        # Überprüfe die max_rounds-Parameter
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    return jsonify({
                        "success": False,
                        "error": t('api.maxRoundsPositive')
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": t('api.maxRoundsInvalid')
                }), 400

        if platform not in ['twitter', 'reddit', 'parallel']:
            return jsonify({
                "success": False,
                "error": t('api.invalidPlatform', platform=platform)
            }), 400

        # Überprüfe, ob die Simulation bereit ist
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        force_restarted = False
        
        # Intelligente Statusbehandlung: Erlaube Neustart, wenn Vorbereitung abgeschlossen ist
        if state.status != SimulationStatus.READY:
            # Überprüfe, ob die Vorbereitung abgeschlossen ist
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)

            if is_prepared:
                # Vorbereitung abgeschlossen, überprüfe auf laufende Prozesse
                if state.status == SimulationStatus.RUNNING:
                    # Überprüfe, ob der Simulationsprozess läuft
                    run_state = SimulationRunner.get_run_state(simulation_id)
                    if run_state and run_state.runner_status.value == "running":
                        # Prozess läuft wirklich
                        if force:
                            # Erzwinge Modus: Stoppe den laufenden Simulationsprozess
                            logger.info(f"Erzwinge Modus: Stoppe den laufenden Simulationsprozess{simulation_id}")
                            try:
                                SimulationRunner.stop_simulation(simulation_id)
                            except Exception as e:
                                logger.warning(f"Warnung beim Stoppen der Simulation: {str(e)}")
                        else:
                            return jsonify({
                                "success": False,
                                "error": t('api.simRunningForceHint')
                            }), 400

                # Wenn im Erzwinge-Modus, bereinige die Laufprotokolle
                if force:
                    logger.info(f"Erzwungener Modus: Simulationsprotokolle bereinigen {simulation_id}")
                    cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
                    if not cleanup_result.get("success"):
                        logger.warning(f"Warnung bei Protokollbereinigung: {cleanup_result.get('errors')}")
                    force_restarted = True

                # Prozess existiert nicht oder ist beendet, setze den Status auf ready
                logger.info(f"Simulation {simulation_id} Vorbereitung abgeschlossen, Status zurückgesetzt auf ready (vorheriger Status: {state.status.value}）")
                state.status = SimulationStatus.READY
                manager._save_simulation_state(state)
            else:
                # Vorbereitung noch nicht abgeschlossen
                return jsonify({
                    "success": False,
                    "error": t('api.simNotReady', status=state.status.value)
                }), 400
        
        # Lese die Graph-ID (für das Updaten des Graphen-Verweises)
        graph_id = None
        if enable_graph_memory_update:
            # Abfragen des graph_id aus der Simulationsstatus oder Projekt
            graph_id = state.graph_id
            if not graph_id:
                # Versuche, aus dem Projekt abzurufen
                project = ProjectManager.get_project(state.project_id)
                if project:
                    graph_id = project.graph_id
            
            if not graph_id:
                return jsonify({
                    "success": False,
                    "error": t('api.graphIdRequiredForMemory')
                }), 400
            
            logger.info(f"Graph-Speicher-Update aktivieren: simulation_id={simulation_id}, graph_id={graph_id}")
        
        # Starte Simulation
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            graph_id=graph_id
        )
        
        # Aktualisiere den Simulationsstatus
        state.status = SimulationStatus.RUNNING
        manager._save_simulation_state(state)
        
        response_data = run_state.to_dict()
        if max_rounds:
            response_data['max_rounds_applied'] = max_rounds
        response_data['graph_memory_update_enabled'] = enable_graph_memory_update
        response_data['force_restarted'] = force_restarted
        if enable_graph_memory_update:
            response_data['graph_id'] = graph_id
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Simulation starten fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """
	Stoppe die Simulation
	
	Anfrage (JSON):
		{
			"simulation_id": "sim_xxxx"  // Pflichtfeld, ID der Simulation
		}
	
	Rückgabe:
		{
			"success": true,
			"data": {
				"simulation_id": "sim_xxxx",
				"runner_status": "stopped",
				"completed_at": "2025-12-01T12:00:00"
			}
		}
	"""
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        run_state = SimulationRunner.stop_simulation(simulation_id)
        
        # Aktualisiere den Simulationsstatus
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Simulation stoppen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Echtzeit-Statusüberwachungskonsole ==============

@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id: str):
    """
    Echtzeit-Status der Simulationsausführung abrufen (für Frontend-Polling)
    
    Rückgabe:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "current_round": 0,
                    "total_rounds": 0,
                    "progress_percent": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            })
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Laufzeitstatus abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id: str):
    """
    Ruft den detaillierten Status der Simulation ab (inklusive aller Aktionen)
    
    Verwendet zur Darstellung von Echtzeitdaten im Frontend
    
    Query-Parameter:
        platform: Filtert die Plattform (twitter/reddit, optional)
    
    Rückgabe:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # Alle Aktionen auf der Twitter-Plattform
                "reddit_actions": [...]    # Alle Aktionen auf der Reddit-Plattform
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get('platform')
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "all_actions": [],
                    "twitter_actions": [],
                    "reddit_actions": []
                }
            })
        
        # Abfragen der vollständigen Aktionen
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter
        )
        
        # Platform-basierte Abfrage von Aktionen
        twitter_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="twitter"
        ) if not platform_filter or platform_filter == "twitter" else []
        
        reddit_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="reddit"
        ) if not platform_filter or platform_filter == "reddit" else []
        
        # Abfragen der aktuellen Rundenaktionen (recent_actions zeigt nur die neueste Runde an)
        current_round = run_state.current_round
        recent_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter,
            round_num=current_round
        ) if current_round > 0 else []
        
        # Abfrage der grundlegenden Statusinformation
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions zeigt nur die neueste Runde für beide Plattformen an
        result["recent_actions"] = [a.to_dict() for a in recent_actions]
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Detailstatus abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_simulation_actions(simulation_id: str):
    """
	Abrufen der Aktionshistorie des Agents in der Simulation
	
	Query-Parameter:
		limit: Anzahl der zurückgegebenen Einträge (Standardwert 100)
		offset: Offset-Wert (Standardwert 0)
		platform: Filterung nach Plattform (twitter/reddit)
		agent_id: Filterung nach Agent-ID
		round_num: Filterung nach Rundennummer
	
	Rückgabe:
		{
			"success": true,
			"data": {
				"count": 100,
				"actions": [...]
			}
		}"""
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)
        
        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(actions),
                "actions": [a.to_dict() for a in actions]
            }
        })
        
    except Exception as e:
        logger.error(f"Aktionsverlauf abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id: str):
    """
    Simulations-Zeitachse abrufen (nach Runden zusammengefasst)
    
    Für Frontend-Fortschrittsbalken und Zeitachsen-Ansicht
    
    Query-Parameter:
        start_round: Startrunde (Standard 0)
        end_round: Endrunde (Standard alle)
    
    Gibt zusammengefasste Informationen pro Runde zurück
    """
    try:
        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)
        
        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            start_round=start_round,
            end_round=end_round
        )
        
        return jsonify({
            "success": True,
            "data": {
                "rounds_count": len(timeline),
                "timeline": timeline
            }
        })
        
    except Exception as e:
        logger.error(f"Zeitachse abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """
	Holt die Statistiken für jeden Agent.
	
	Zur Darstellung der Aktivitätsrangliste von Agents, der Verteilung von Aktionen usw. für das Frontend."""
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)
        
        return jsonify({
            "success": True,
            "data": {
                "agents_count": len(stats),
                "stats": stats
            }
        })
        
    except Exception as e:
        logger.error(f"Agent-Statistik abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Datenbankabfragekonsole ==============

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id: str):
    """
    Beiträge aus der Simulation abrufen
    
    Query-Parameter:
        platform: Plattformtyp (twitter/reddit)
        limit: Anzahl der Ergebnisse (Standard 50)
        offset: Versatz
    
    Gibt Beitragsliste zurück (aus SQLite-Datenbank gelesen)
    """
    try:
        platform = request.args.get('platform', 'reddit')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "platform": platform,
                    "count": 0,
                    "posts": [],
                    "message": t('api.dbNotExist')
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM post 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            posts = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT COUNT(*) FROM post")
            total = cursor.fetchone()[0]
            
        except sqlite3.OperationalError:
            posts = []
            total = 0
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "total": total,
                "count": len(posts),
                "posts": posts
            }
        })
        
    except Exception as e:
        logger.error(f"Beiträge abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/comments', methods=['GET'])
def get_simulation_comments(simulation_id: str):
    """
	Hole Kommentare aus der Simulation (nur Reddit)
	
	Query Parameter:
		post_id: Filter Post ID (optional)
		limit: Anzahl der zurückgegebenen Elemente
		offset: Offset"""
    try:
        post_id = request.args.get('post_id')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_path = os.path.join(sim_dir, "reddit_simulation.db")
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "count": 0,
                    "comments": []
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if post_id:
                cursor.execute("""
                    SELECT * FROM comment 
                    WHERE post_id = ?
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (post_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM comment 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            comments = [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.OperationalError:
            comments = []
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(comments),
                "comments": comments
            }
        })
        
    except Exception as e:
        logger.error(f"Kommentare abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interview-Abfragekonsole ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    Interview eines einzelnen Agents

    Hinweis: Diese Funktion erfordert, dass die Simulationsumgebung im Laufzustand ist (wartet nach Abschluss des Simulationszyklus auf Befehle).

    Anfrage (JSON):
        {
            "simulation_id": "sim_xxxx",       // Pflichtfeld, ID der Simulation
            "agent_id": 0,                     // Pflichtfeld, Agent-ID
            "prompt": "Was ist deine Meinung dazu?",  // Pflichtfeld, Interviewfrage
            "platform": "twitter",             // Optional, spezifiziert die Plattform (twitter/reddit)
                                                  // Wenn nicht spezifiziert: Dual-Plattform-Simulation mit gleichzeitigen Interviews auf beiden Plattformen
            "timeout": 60                      // Optional, Zeitlimit (Sekunden), Standardwert ist 60
        }

    Rückgabe (wenn keine Plattform spezifiziert wurde, Dual-Plattform-Modus):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "Was ist deine Meinung dazu?",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    Rückgabe (wenn eine Plattform spezifiziert wurde):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "Was ist deine Meinung dazu?",
                "result": {
                    "agent_id": 0,
                    "response": "Ich denke...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 60)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        if agent_id is None:
            return jsonify({
                "success": False,
                "error": t('api.requireAgentId')
            }), 400
        
        if not prompt:
            return jsonify({
                "success": False,
                "error": t('api.requirePrompt')
            }), 400
        
        # Validiere die platform-Parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400
        
        # Überprüfe den Umgebungsstatus
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400
        
        # Optimiere das prompt, füge einen Präfix hinzu, um die Agent-Aufrufe zu vermeiden
        optimized_prompt = optimize_interview_prompt(prompt)
        
        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.interviewTimeout', error=str(e))
        }), 504
        
    except Exception as e:
        logger.error(f"Interview fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    Mehrere Agenten in einem Batch interviewen

    Hinweis: Diese Funktion erfordert, dass die Simulationsumgebung im Laufzustand ist.

    Anfrage (JSON):
        {
            "simulation_id": "sim_xxxx",       // Pflichtfeld, ID der Simulation
            "interviews": [                    // Pflichtfeld, Liste der Interviews
                {
                    "agent_id": 0,
                    "prompt": "Was ist deine Meinung zu A?",
                    "platform": "twitter"      // Optional, gibt das Interview-Platform für diesen Agenten an
                },
                {
                    "agent_id": 1,
                    "prompt": "Was ist deine Meinung zu B?"  // Wenn platform nicht angegeben wird, wird der Standardwert verwendet
                }
            ],
            "platform": "reddit",              // Optional, Standard-Platform (wird von jedem Eintrag im platform-Feld überschrieben)
                                               // Wenn nicht angegeben: Doppelte Plattform-Simulation, bei der jeder Agent gleichzeitig auf zwei Plattformen interviewt wird
            "timeout": 120                     // Optional, Zeitlimit (in Sekunden), Standardwert ist 120
        }

    Rückgabe:
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        interviews = data.get('interviews')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 120)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": t('api.requireInterviews')
            }), 400

        # Validiere die platform-Parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400

        # Validiere jedes Interviewelement
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListMissingAgentId', index=i+1)
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListMissingPrompt', index=i+1)
                }), 400
            # Validiere die platform (falls vorhanden) für jedes Element
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": t('api.interviewListInvalidPlatform', index=i+1)
                }), 400

        # Überprüfe den Umgebungsstatus
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400

        # Optimiere das prompt für jedes Interviewelement, füge einen Präfix hinzu, um die Agent-Aufrufe zu vermeiden
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.batchInterviewTimeout', error=str(e))
        }), 504

    except Exception as e:
        logger.error(f"Batch-Interview fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/all', methods=['POST'])
def interview_all_agents():
    """
    Globale Interviews - Alle Agenten werden mit der gleichen Frage befragt

    Hinweis: Diese Funktion erfordert, dass das Simulationsumfeld aktiv ist.

    Anfrage (JSON):
        {
            "simulation_id": "sim_xxxx",            // Pflichtfeld, ID des Simulationslaufs
            "prompt": "Was ist Ihre allgemeine Meinung dazu?",  // Pflichtfeld, Interviewfragen für alle Agenten
            "platform": "reddit",                   // Optional, spezifiziert die Plattform (twitter/reddit)
                                                        // Wenn nicht angegeben: Doppelplattform-Simulation, bei der jeder Agent gleichzeitig auf beiden Plattformen befragt wird.
            "timeout": 180                          // Optional, Zeitlimit in Sekunden, Standardwert ist 180
        }

    Rückgabe:
        {
            "success": true,
            "data": {
                "interviews_count": 50,
                "result": {
                    "interviews_count": 100,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        ...
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 180)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": t('api.requirePrompt')
            }), 400

        # Validiere die platform-Parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": t('api.invalidInterviewPlatform')
            }), 400

        # Überprüfe den Umgebungsstatus
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": t('api.envNotRunning')
            }), 400

        # Optimiere das prompt, füge einen Präfix hinzu, um die Agent-Aufrufe zu vermeiden
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_all_agents(
            simulation_id=simulation_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": t('api.globalInterviewTimeout', error=str(e))
        }), 504

    except Exception as e:
        logger.error(f"Globales Interview fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/history', methods=['POST'])
def get_interview_history():
    """
    Interview-Verlauf abrufen

    Liest alle Interview-Einträge aus der Simulationsdatenbank

    Anfrage (JSON):
        {
            "simulation_id": "sim_xxxx",  // Pflicht, Simulations-ID
            "platform": "reddit",          // Optional, Plattformtyp (reddit/twitter)
                                           // Ohne Angabe werden alle Plattformen zurückgegeben
            "agent_id": 0,                 // Optional, nur Interviews dieses Agents abrufen
            "limit": 100                   // Optional, Anzahl der Ergebnisse, Standard 100
        }

    Rückgabe:
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "Ich denke...",
                        "prompt": "Was halten Sie davon?",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        platform = data.get('platform')  # Keine Angabe bedeutet Rückgabe der Geschichte für beide Plattformen
        agent_id = data.get('agent_id')
        limit = data.get('limit', 100)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"Interview-Verlauf abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/env-status', methods=['POST'])
def get_env_status():
    """
    Simulationsumgebungsstatus abrufen

    Prüft ob die Simulationsumgebung aktiv ist (Interview-Befehle empfangen kann)

    Anfrage (JSON):
        {
            "simulation_id": "sim_xxxx"  // Pflicht, Simulations-ID
        }

    Rückgabe:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "Umgebung läuft, kann Interview-Befehle empfangen"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        env_alive = SimulationRunner.check_env_alive(simulation_id)
        
        # Abfrage von detaillierter Statusinformation
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = t('api.envRunning')
        else:
            message = t('api.envNotRunningShort')

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"Umgebungsstatus abrufen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
	Schliët das Simulationsumgebung
	
	Sendet dem Simulator den Befehl, umvorsichtig die Umgebung zu schliëen und aus der Wartezeitmodus zu gehen.
	
	Hinweis: Dies unterscheidet sich von dem /stop-Interface. Das /stop-Interface beendet den Prozess zwangsweise,
während dieses Interface das Simulationsumgebung elegant schliët und beendet.
	
	Anfrage (JSON):
	{
		"simulation_id": "sim_xxxx",  // Pflichtfeld, ID des Simulators
		"timeout": 30                  // Optional, Zeitlimit (Sekunden), Standardwert ist 30
	}
	
	Rückgabe:
	{
		"success": true,
		"data": {
			"message": "Befehl zum Schliëen der Umgebung wurde gesendet",
			"result": {...},
			"timestamp": "2025-12-08T10:00:01"
		}
	}"""
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        timeout = data.get('timeout', 30)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400
        
        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )
        
        # Aktualisiere den Simulationsstatus
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.COMPLETED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Umgebung schließen fehlgeschlagen: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
