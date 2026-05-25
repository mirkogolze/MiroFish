"""
OASIS simulation runner
Run simulations in the background and record actions of each Agent, supports real-time status monitoring
"""

import os
import sys
import json
import time
import asyncio
import threading
import subprocess
import signal
import atexit
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale
from .zep_graph_memory_updater import ZepGraphMemoryManager
from .simulation_ipc import SimulationIPCClient, CommandType, IPCResponse

logger = get_logger('mirofish.simulation_runner')

# Markierung, ob Bereinigungs-Funktion registriert wurde
_cleanup_registered = False

# Platform-Überprüfung
IS_WINDOWS = sys.platform == 'win32'


class RunnerStatus(str, Enum):
    """Runner-Status"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent-Aktionen protokollieren"""
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """Zusammenfassung pro Runde"""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """Simulationslaufstatus (Echtzeit)"""
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE
    
    # Fortschrittsinformationen
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0
    
    # Unabhängige Runden und Simulationszeiten für jede Plattform (für die parallele Anzeige auf beiden Plattformen)
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    
    # Platform-Status
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    
    # Simulationserfolgsstatus (durch Überprüfung des simulation_end-Ereignisses in actions.jsonl)
    twitter_completed: bool = False
    reddit_completed: bool = False
    
    # Zusammenfassung pro Runde
    rounds: List[RoundSummary] = field(default_factory=list)
    
    # Letzte Aktionen (für die Echtzeitanzeige im Frontend)
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50
    
    # Zeitstempel
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    # Fehlerinformationen
    error: Optional[str] = None
    
    # Prozess-ID (für das Stoppen)
    process_pid: Optional[int] = None
    
    def add_action(self, action: AgentAction):
        """Aktion hinzufügen zu der Liste der neuesten Aktionen"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[:self.max_recent_actions]
        
        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1
        
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # Unabhängige Runden und Zeiten für jede Plattform
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }
    
    def to_detail_dict(self) -> Dict[str, Any]:
        """Details über die letzte Aktion enthalten"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    Simulation runner
    
    Responsibilities:
    1. Run OASIS simulations in background processes
    2. Parse run logs, record actions of each Agent
    3. Provide real-time status query interfaces
    4. Support pause/stop/resume operations
    """
    
    # Speicherort der Statusdaten
    RUN_STATE_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    # Skriptverzeichnis
    SCRIPTS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../scripts'
    )
    
    # In-Memory-Status
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {}  # Speichere stdout-Dateihandle
    _stderr_files: Dict[str, Any] = {}  # Speichere stderr-Dateihandle
    
    # Graph-Memory-Updater-Konfiguration
    _graph_memory_enabled: Dict[str, bool] = {}  # simulation_id -> enabled
    
    @classmethod
    def get_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """Hole Simulationslaufstatus"""
        if simulation_id in cls._run_states:
            return cls._run_states[simulation_id]
        
        # Versuche aus Datei zu laden
        state = cls._load_run_state(simulation_id)
        if state:
            cls._run_states[simulation_id] = state
        return state
    
    @classmethod
    def _load_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """Simulationslaufstatus aus Datei laden"""
        state_file = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
        if not os.path.exists(state_file):
            return None
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = SimulationRunState(
                simulation_id=simulation_id,
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # Unabhängige Runden und Zeiten für jede Plattform
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )
            
            # Lade letzte Aktionen
            actions_data = data.get("recent_actions", [])
            for a in actions_data:
                state.recent_actions.append(AgentAction(
                    round_num=a.get("round_num", 0),
                    timestamp=a.get("timestamp", ""),
                    platform=a.get("platform", ""),
                    agent_id=a.get("agent_id", 0),
                    agent_name=a.get("agent_name", ""),
                    action_type=a.get("action_type", ""),
                    action_args=a.get("action_args", {}),
                    result=a.get("result"),
                    success=a.get("success", True),
                ))
            
            return state
        except Exception as e:
            logger.error(f"Laufzeitstatus laden fehlgeschlagen: {str(e)}")
            return None
    
    @classmethod
    def _save_run_state(cls, state: SimulationRunState):
        """Speichere Simulationslaufstatus in Datei"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        state_file = os.path.join(sim_dir, "run_state.json")
        
        data = state.to_detail_dict()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        cls._run_states[state.simulation_id] = state
    
    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None,  # Maximale Anzahl von Simulationsschritten (optional, um zu lange Simulatoren abzubrechen)
        enable_graph_memory_update: bool = False,  # Aktivitäten aktualisieren auf Zep-Graph
        graph_id: str = None  # Zep-Graph-ID (erforderlich, wenn Graph-Aktualisierung aktiviert ist)
    ) -> SimulationRunState:
        """
        Start simulation
        
        Args:
            simulation_id: Simulation ID
            platform: Running platform (twitter/reddit/parallel)
            max_rounds: Maximum number of simulation rounds (optional, used to truncate overly long simulations)
            enable_graph_memory_update: Whether to dynamically update the Zep graph with Agent activities
            graph_id: Zep graph ID (required if enabling graph updates)
        
        Returns:
            SimulationRunState
        """
        # Überprüfe ob bereits läuft
        existing = cls.get_run_state(simulation_id)
        if existing and existing.runner_status in [RunnerStatus.RUNNING, RunnerStatus.STARTING]:
            raise ValueError(f"Simulation läuft bereits: {simulation_id}")
        
        # Lade Simulationseinstellungen
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            raise ValueError(f"Simulationskonfiguration existiert nicht, bitte zuerst /prepare aufrufen")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Initialisiere Laufstatus
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)
        
        # Wenn maximale Schritte angegeben sind, abbrechen
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(f"Rundenzahl gekürzt: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
        
        state = SimulationRunState(
            simulation_id=simulation_id,
            runner_status=RunnerStatus.STARTING,
            total_rounds=total_rounds,
            total_simulation_hours=total_hours,
            started_at=datetime.now().isoformat(),
        )
        
        cls._save_run_state(state)
        
        # Erstelle Updater wenn Graph-Aktualisierung aktiviert ist
        if enable_graph_memory_update:
            if not graph_id:
                raise ValueError("Bei aktivierter Graph-Verinnerungsmethode muss ein graph_id bereitgestellt werden")
            
            try:
                ZepGraphMemoryManager.create_updater(simulation_id, graph_id)
                cls._graph_memory_enabled[simulation_id] = True
                logger.info(f"Graph-Speicher-Update aktiviert: simulation_id={simulation_id}, graph_id={graph_id}")
            except Exception as e:
                logger.error(f"Graph-Speicher-Updater erstellen fehlgeschlagen: {e}")
                cls._graph_memory_enabled[simulation_id] = False
        else:
            cls._graph_memory_enabled[simulation_id] = False
        
        # Bestimme welches Skript ausgeführt wird (Skripte befinden sich im backend/scripts/ Verzeichnis)
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True
        
        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)
        
        if not os.path.exists(script_path):
            raise ValueError(f"Skript existiert nicht: {script_path}")
        
        # Erstelle Aktionen-Queue
        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue
        
        # Starte Simulationsprozess
        try:
            # Erstelle Laufbefehl mit vollständigem Pfad
            # Neue Log-Struktur:
            # twitter/actions.jsonl - Twitter-Aktionen-Log
            # reddit/actions.jsonl  - Reddit-Aktionen-Log
            # simulation.log        - Hauptprozess-Log
            
            cmd = [
                sys.executable,  # Python-Interpreter
                script_path,
                "--config", config_path,  # Verwende vollständigen Konfigurationsdateipfad
            ]
            
            # Füge maximale Schritte hinzu, wenn angegeben
            if max_rounds is not None and max_rounds > 0:
                cmd.extend(["--max-rounds", str(max_rounds)])
            
            # Erstelle Hauptlogdatei, um zu verhindern dass stdout/stderr-Pipeline-Buffers voll werden und den Prozess blockieren
            main_log_path = os.path.join(sim_dir, "simulation.log")
            main_log_file = open(main_log_path, 'w', encoding='utf-8')
            
            # Setze Subprozess-Umgebungsvariablen, um sicherzustellen dass UTF-8 auf Windows verwendet wird
            # Dies kann Probleme mit Drittanbieter-Bibliotheken (wie OASIS) lösen, die Dateien ohne angegebenes Encoding lesen
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'  # Python 3.7+ unterstützt, damit alle open() standardmäßig UTF-8 verwenden
            env['PYTHONIOENCODING'] = 'utf-8'  # Sicherstellen dass stdout/stderr UTF-8 verwenden
            
            # Setze Arbeitsverzeichnis auf Simulationsverzeichnis (Datenbanken etc. werden hier erstellt)
            # Erstelle neuen Prozessgruppe mit start_new_session=True, um sicherzustellen dass alle Subprozesse durch os.killpg beendet werden können
            process = subprocess.Popen(
                cmd,
                cwd=sim_dir,
                stdout=main_log_file,
                stderr=subprocess.STDOUT,  # stderr auch in die gleiche Datei schreiben
                text=True,
                encoding='utf-8',  # Explizit angegebenes Encoding
                bufsize=1,
                env=env,  # Übertrage Umgebungsvariablen mit UTF-8-Einstellungen
                start_new_session=True,  # Erstelle neue Prozessgruppe, um sicherzustellen dass alle relevanten Prozesse beendet werden können wenn der Server geschlossen wird
            )
            
            # Speichere Dateihandle für spätere Schließung
            cls._stdout_files[simulation_id] = main_log_file
            cls._stderr_files[simulation_id] = None  # Kein separates stderr mehr benötigt
            
            state.process_pid = process.pid
            state.runner_status = RunnerStatus.RUNNING
            cls._processes[simulation_id] = process
            cls._save_run_state(state)
            
            # Capture locale before spawning monitor thread
            current_locale = get_locale()

            # Starte Überwachungs-Thread
            monitor_thread = threading.Thread(
                target=cls._monitor_simulation,
                args=(simulation_id, current_locale),
                daemon=True
            )
            monitor_thread.start()
            cls._monitor_threads[simulation_id] = monitor_thread
            
            logger.info(f"Simulation erfolgreich gestartet: {simulation_id}, pid={process.pid}, platform={platform}")
            
        except Exception as e:
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
            raise
        
        return state
    
    @classmethod
    def _monitor_simulation(cls, simulation_id: str, locale: str = 'zh'):
        """Überwache Simulationsprozess, analysiere Aktionen-Protokoll"""
        set_locale(locale)
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        # Neue Log-Struktur: Plattform-spezifische Aktionen-Logs
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        process = cls._processes.get(simulation_id)
        state = cls.get_run_state(simulation_id)
        
        if not process or not state:
            return
        
        twitter_position = 0
        reddit_position = 0
        
        try:
            while process.poll() is None:  # Prozess läuft noch
                # Lese Twitter-Aktionsprotokolle
                if os.path.exists(twitter_actions_log):
                    twitter_position = cls._read_action_log(
                        twitter_actions_log, twitter_position, state, "twitter"
                    )
                
                # Lese Reddit-Aktionsprotokolle
                if os.path.exists(reddit_actions_log):
                    reddit_position = cls._read_action_log(
                        reddit_actions_log, reddit_position, state, "reddit"
                    )
                
                # Status aktualisieren
                cls._save_run_state(state)
                time.sleep(2)
            
            # Nach dem Prozessende das Protokoll noch einmal lesen
            if os.path.exists(twitter_actions_log):
                cls._read_action_log(twitter_actions_log, twitter_position, state, "twitter")
            if os.path.exists(reddit_actions_log):
                cls._read_action_log(reddit_actions_log, reddit_position, state, "reddit")
            
            # Prozessende
            exit_code = process.returncode
            
            if exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = datetime.now().isoformat()
                logger.info(f"Simulation abgeschlossen: {simulation_id}")
            else:
                state.runner_status = RunnerStatus.FAILED
                # Fehlermeldungen aus dem Hauptprotokoll lesen
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, 'r', encoding='utf-8') as f:
                            error_info = f.read()[-2000:]  # Letzte 2000 Zeichen verwenden
                except Exception:
                    pass
                state.error = f"Prozess-Exit-Code: {exit_code}, Fehler: {error_info}"
                logger.error(f"Simulation fehlgeschlagen: {simulation_id}, error={state.error}")
            
            state.twitter_running = False
            state.reddit_running = False
            cls._save_run_state(state)
            
        except Exception as e:
            logger.error(f"Überwachungsthread-Fehler: {simulation_id}, error={str(e)}")
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
        
        finally:
            # Stoppe das Graphen-Update-System
            if cls._graph_memory_enabled.get(simulation_id, False):
                try:
                    ZepGraphMemoryManager.stop_updater(simulation_id)
                    logger.info(f"Graph-Speicher-Update gestoppt: simulation_id={simulation_id}")
                except Exception as e:
                    logger.error(f"Graph-Speicher-Updater stoppen fehlgeschlagen: {e}")
                cls._graph_memory_enabled.pop(simulation_id, None)
            
            # Ressourcen des Prozesses bereinigen
            cls._processes.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)
            
            # Schließe Protokolldateihandles
            if simulation_id in cls._stdout_files:
                try:
                    cls._stdout_files[simulation_id].close()
                except Exception:
                    pass
                cls._stdout_files.pop(simulation_id, None)
            if simulation_id in cls._stderr_files and cls._stderr_files[simulation_id]:
                try:
                    cls._stderr_files[simulation_id].close()
                except Exception:
                    pass
                cls._stderr_files.pop(simulation_id, None)
    
    @classmethod
    def _read_action_log(
        cls, 
        log_path: str, 
        position: int, 
        state: SimulationRunState,
        platform: str
    ) -> int:
        """
        Read action log file
        
        Args:
            log_path: Path to the log file
            position: Last read position
            state: Run status object
            platform: Platform name (twitter/reddit)
        
        Returns:
            New read position
        """
        # Überprüfe, ob das Graphen-Update aktiviert ist
        graph_memory_enabled = cls._graph_memory_enabled.get(state.simulation_id, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = ZepGraphMemoryManager.get_updater(state.simulation_id)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            action_data = json.loads(line)
                            
                            # Verarbeite Einträge für Ereignistypen
                            if "event_type" in action_data:
                                event_type = action_data.get("event_type")
                                
                                # Detektiere simulation_end-Ereignisse, markiere Plattform als abgeschlossen
                                if event_type == "simulation_end":
                                    if platform == "twitter":
                                        state.twitter_completed = True
                                        state.twitter_running = False
                                        logger.info(f"Twitter-Simulation abgeschlossen: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    elif platform == "reddit":
                                        state.reddit_completed = True
                                        state.reddit_running = False
                                        logger.info(f"Reddit-Simulation abgeschlossen: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    
                                    # Überprüfe, ob alle aktiven Plattformen abgeschlossen sind
                                    # Wenn nur eine Plattform läuft, überprüfe nur diese
                                    # Wenn zwei Plattformen laufen, müssen beide abgeschlossen sein
                                    all_completed = cls._check_all_platforms_completed(state)
                                    if all_completed:
                                        state.runner_status = RunnerStatus.COMPLETED
                                        state.completed_at = datetime.now().isoformat()
                                        logger.info(f"Simulation auf allen Plattformen abgeschlossen: {state.simulation_id}")
                                
                                # Aktualisiere Rundeninformation (aus round_end-Ereignis)
                                elif event_type == "round_end":
                                    round_num = action_data.get("round", 0)
                                    simulated_hours = action_data.get("simulated_hours", 0)
                                    
                                    # Aktualisiere die unabhängigen Runden und Zeiten für jede Plattform
                                    if platform == "twitter":
                                        if round_num > state.twitter_current_round:
                                            state.twitter_current_round = round_num
                                        state.twitter_simulated_hours = simulated_hours
                                    elif platform == "reddit":
                                        if round_num > state.reddit_current_round:
                                            state.reddit_current_round = round_num
                                        state.reddit_simulated_hours = simulated_hours
                                    
                                    # Gesamte Runde ist das Maximum der beiden Plattformen
                                    if round_num > state.current_round:
                                        state.current_round = round_num
                                    # Gesamtzeit ist das Maximum der beiden Plattformen
                                    state.simulated_hours = max(state.twitter_simulated_hours, state.reddit_simulated_hours)
                                
                                continue
                            
                            action = AgentAction(
                                round_num=action_data.get("round", 0),
                                timestamp=action_data.get("timestamp", datetime.now().isoformat()),
                                platform=platform,
                                agent_id=action_data.get("agent_id", 0),
                                agent_name=action_data.get("agent_name", ""),
                                action_type=action_data.get("action_type", ""),
                                action_args=action_data.get("action_args", {}),
                                result=action_data.get("result"),
                                success=action_data.get("success", True),
                            )
                            state.add_action(action)
                            
                            # Aktualisiere die Runde
                            if action.round_num and action.round_num > state.current_round:
                                state.current_round = action.round_num
                            
                            # Wenn das Graphen-Update aktiviert ist, sende Aktivität an Zep
                            if graph_updater:
                                graph_updater.add_activity_from_dict(action_data, platform)
                            
                        except json.JSONDecodeError:
                            pass
                return f.tell()
        except Exception as e:
            logger.warning(f"Aktionsprotokoll lesen fehlgeschlagen: {log_path}, error={e}")
            return position
    
    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
        Check if all enabled platforms have completed the simulation
        
        Determine by checking whether the corresponding actions.jsonl file exists
        
        Returns:
            True if all enabled platforms are complete
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        # Überprüfe, welche Plattformen aktiviert sind (durch Überprüfung der Existenz von Dateien)
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)
        
        # Wenn eine Plattform aktiviert ist aber nicht abgeschlossen, gib False zurück
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False
        
        # Mindestens eine Plattform ist aktiviert und abgeschlossen
        return twitter_enabled or reddit_enabled
    
    @classmethod
    def _terminate_process(cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10):
        """
        Terminate process and its children across platforms
        
        Args:
            process: Process to terminate
            simulation_id: Simulation ID (for logging)
            timeout: Timeout period for waiting the process to exit (seconds)
        """
        if IS_WINDOWS:
            # Windows: Verwende taskkill-Befehl zum Beenden des Prozessbaums
            # /F = Zwinge das Programm zu beenden, /T = Beende den gesamten Prozessbaum (inklusive Subprozesse)
            logger.info(f"Prozessbaum beenden (Windows): simulation={simulation_id}, pid={process.pid}")
            try:
                # Versuche zunächst eine elegante Beendigung
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T'],
                    capture_output=True,
                    timeout=5
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Zwinge das Programm zu beenden
                    logger.warning(f"Prozess antwortet nicht, erzwungene Beendigung: {simulation_id}")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(process.pid), '/T'],
                        capture_output=True,
                        timeout=5
                    )
                    process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"taskkill fehlgeschlagen, versuche terminate: {e}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        else:
            # Unix: Verwende Prozessgruppen zum Beenden
            # Da start_new_session=True verwendet wird, ist die Prozessgruppen-ID gleich der PID des Hauptprozesses
            pgid = os.getpgid(process.pid)
            logger.info(f"Prozessgruppe beenden (Unix): simulation={simulation_id}, pgid={pgid}")
            
            # Sendiere SIGTERM an die gesamte Prozessgruppe
            os.killpg(pgid, signal.SIGTERM)
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Wenn nach der Zeitablauf noch nicht beendet, sendiere SIGKILL
                logger.warning(f"Prozessgruppe reagiert nicht auf SIGTERM, erzwungene Beendigung: {simulation_id}")
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)
    
    @classmethod
    def stop_simulation(cls, simulation_id: str) -> SimulationRunState:
        """Simulierung stoppen"""
        state = cls.get_run_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation existiert nicht: {simulation_id}")
        
        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(f"Simulation läuft nicht: {simulation_id}, status={state.runner_status}")
        
        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)
        
        # Beende den Prozess
        process = cls._processes.get(simulation_id)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, simulation_id)
            except ProcessLookupError:
                # Der Prozess existiert nicht mehr
                pass
            except Exception as e:
                logger.error(f"Prozessgruppe beenden fehlgeschlagen: {simulation_id}, error={e}")
                # Rücke auf direktes Beenden des Prozesses zurück
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
        
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = datetime.now().isoformat()
        cls._save_run_state(state)
        
        # Stoppe das Graphen-Update-System
        if cls._graph_memory_enabled.get(simulation_id, False):
            try:
                ZepGraphMemoryManager.stop_updater(simulation_id)
                logger.info(f"Graph-Speicher-Update gestoppt: simulation_id={simulation_id}")
            except Exception as e:
                logger.error(f"Graph-Speicher-Updater stoppen fehlgeschlagen: {e}")
            cls._graph_memory_enabled.pop(simulation_id, None)
        
        logger.info(f"Simulation gestoppt: {simulation_id}")
        return state
    
    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Read actions from a single action file
        
        Args:
            file_path: Path to the action log file
            default_platform: Default platform (used when the action record does not contain a platform field)
            platform_filter: Platform filter
            agent_id: Agent ID filter
            round_num: Round number filter
        """
        if not os.path.exists(file_path):
            return []
        
        actions = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Überspringe Nicht-Aktions-Einträge (wie simulation_start, round_start, round_end usw.)
                    if "event_type" in data:
                        continue
                    
                    # Überspringe Einträge ohne agent_id (nicht Agent-Aktionen)
                    if "agent_id" not in data:
                        continue
                    
                    # Holte Plattform: Priorisiere die in den Aufzeichnungen enthaltene platform, ansonsten verwende Standardplattform
                    record_platform = data.get("platform") or default_platform or ""
                    
                    # Filtere
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue
                    
                    actions.append(AgentAction(
                        round_num=data.get("round", 0),
                        timestamp=data.get("timestamp", ""),
                        platform=record_platform,
                        agent_id=data.get("agent_id", 0),
                        agent_name=data.get("agent_name", ""),
                        action_type=data.get("action_type", ""),
                        action_args=data.get("action_args", {}),
                        result=data.get("result"),
                        success=data.get("success", True),
                    ))
                    
                except json.JSONDecodeError:
                    continue
        
        return actions
    
    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Get complete action history for all platforms (no pagination limit)
        
        Args:
            simulation_id: Simulation ID
            platform: Platform filter (twitter/reddit)
            agent_id: Agent ID filter
            round_num: Round number filter
            
        Returns:
            Complete list of actions (sorted by timestamp, newer first)
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        actions = []
        
        # Lese Twitter-Aktionsdatei (setze automatisch platform auf twitter basierend auf dem Dateipfad)
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(cls._read_actions_from_file(
                twitter_actions_log,
                default_platform="twitter",  # Automatisches Füllen des platform-Feldes
                platform_filter=platform,
                agent_id=agent_id, 
                round_num=round_num
            ))
        
        # Lese Reddit-Aktionen-Datei (setze automatisch platform auf reddit)
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(cls._read_actions_from_file(
                reddit_actions_log,
                default_platform="reddit",  # Automatisches Füllen des platform-Feldes
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            ))
        
        # Versuche alte Dateiformate zu lesen, wenn separate Plattformdateien nicht existieren
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None,  # Altes Format sollte platform-Feld enthalten
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            )
        
        # Sortiere nach Zeitstempel (neueste zuerst)
        actions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return actions
    
    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        Get action history (with pagination)
        
        Args:
            simulation_id: Simulation ID
            limit: Limit on the number of returned items
            offset: Offset
            platform: Platform filter
            agent_id: Agent ID filter
            round_num: Round number filter
            
        Returns:
            List of actions
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        # Paging
        return actions[offset:offset + limit]
    
    @classmethod
    def get_timeline(
        cls,
        simulation_id: str,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Erhalte die Simulationszeitlinie (aggregiert nach Runden)
        
        Args:
            simulation_id: Simulations-ID
            start_round: Start-Runde
            end_round: End-Runde
            
        Returns:
            Aggregierte Informationen pro Runde
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        # Gruppiere nach Runden
        rounds: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            round_num = action.round_num
            
            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue
            
            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            r = rounds[round_num]
            
            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1
            
            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = r["action_types"].get(action.action_type, 0) + 1
            r["last_action_time"] = action.timestamp
        
        # Konvertiere in Liste
        result = []
        for round_num in sorted(rounds.keys()):
            r = rounds[round_num]
            result.append({
                "round_num": round_num,
                "twitter_actions": r["twitter_actions"],
                "reddit_actions": r["reddit_actions"],
                "total_actions": r["twitter_actions"] + r["reddit_actions"],
                "active_agents_count": len(r["active_agents"]),
                "active_agents": list(r["active_agents"]),
                "action_types": r["action_types"],
                "first_action_time": r["first_action_time"],
                "last_action_time": r["last_action_time"],
            })
        
        return result
    
    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> List[Dict[str, Any]]:
        """
        Erhalte die Statistikinformationen für jeden Agent
        
        Returns:
            Liste der Agent-Statistiken
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        agent_stats: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            agent_id = action.agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            stats = agent_stats[agent_id]
            stats["total_actions"] += 1
            
            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1
            
            stats["action_types"][action.action_type] = stats["action_types"].get(action.action_type, 0) + 1
            stats["last_action_time"] = action.timestamp
        
        # Sortiere nach Gesamtzahl von Aktionen
        result = sorted(agent_stats.values(), key=lambda x: x["total_actions"], reverse=True)
        
        return result
    
    @classmethod
    def cleanup_simulation_logs(cls, simulation_id: str) -> Dict[str, Any]:
        """
        Bereinige die Laufzeit-Logs der Simulation (für eine erzwungene Neustart)
        
        Entfernt folgende Dateien:
        - run_state.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.db (Simulations-Datenbank)
        - reddit_simulation.db (Simulations-Datenbank)
        - env_status.json (Umgebungszustand)
        
        Hinweis: Konfigurationsdateien (simulation_config.json) und Profildateien werden nicht gelöscht
        
        Args:
            simulation_id: Simulations-ID
            
        Returns:
            Bereinigungs-Informationen
        """
        import shutil
        
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return {"success": True, "message": "Simulationsverzeichnis existiert nicht, kein Aufräumen erforderlich"}
        
        cleaned_files = []
        errors = []
        
        # Liste der zu löschenden Dateien (inklusive Datenbankdateien)
        files_to_delete = [
            "run_state.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db",  # Twitter-Plattform-Datenbank
            "reddit_simulation.db",   # Reddit-Plattform-Datenbank
            "env_status.json",        # Umgebungszustandsdatei
        ]
        
        # Liste der zu löschenden Verzeichnisse (inklusive Aktionen-Protokolle)
        dirs_to_clean = ["twitter", "reddit"]
        
        # Lösche Dateien
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except Exception as e:
                    errors.append(f"Lösche {filename} fehlgeschlagen: {str(e)}")
        
        # Aufräumen der Aktionen-Protokolle im Plattformverzeichnis
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                actions_file = os.path.join(dir_path, "actions.jsonl")
                if os.path.exists(actions_file):
                    try:
                        os.remove(actions_file)
                        cleaned_files.append(f"{dir_name}/actions.jsonl")
                    except Exception as e:
                        errors.append(f"Lösche {dir_name}/actions.jsonl fehlgeschlagen: {str(e)}")
        
        # Aufräumen des Zustands in der Arbeitsspeicher
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]
        
        logger.info(f"Simulationsprotokolle bereinigt: {simulation_id}, Datei löschen: {cleaned_files}")
        
        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None
        }
    
    # Verhindere doppelten Aufräumvorgang
    _cleanup_done = False
    
    @classmethod
    def cleanup_all_simulations(cls):
        """
        Bereinige alle laufenden Simulations-Prozesse
        
        Wird aufgerufen beim Herunterfahren des Servers, um sicherzustellen, dass alle Prozesse beendet werden.
        """
        # Verhindere doppelte Aufräumaktionen
        if cls._cleanup_done:
            return
        cls._cleanup_done = True
        
        # Überprüfe, ob es Inhalte gibt die aufgeräumt werden müssen (vermeide unnötige Protokolle)
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)
        
        if not has_processes and not has_updaters:
            return  # Keine Inhalte zum Aufräumen, stille Rückgabe
        
        logger.info("Aufräumen aller Simulationsprozesse...")
        
        # Stoppe alle Graphen-Updates zuerst (stop_all druckt Protokolle)
        try:
            ZepGraphMemoryManager.stop_all()
        except Exception as e:
            logger.error(f"Graph-Speicher-Updater stoppen fehlgeschlagen: {e}")
        cls._graph_memory_enabled.clear()
        
        # Kopiere Dictionary um Änderungen während der Iteration zu verhindern
        processes = list(cls._processes.items())
        
        for simulation_id, process in processes:
            try:
                if process.poll() is None:  # Prozess läuft noch
                    logger.info(f"Simulationsprozess beenden: {simulation_id}, pid={process.pid}")
                    
                    try:
                        # Verwende plattformübergreifendes Methode zum Beenden des Prozesses
                        cls._terminate_process(process, simulation_id, timeout=5)
                    except (ProcessLookupError, OSError):
                        # Prozess könnte nicht mehr existieren, versuche direktes Beenden
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()
                    
                    # Aktualisiere run_state.json
                    state = cls.get_run_state(simulation_id)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = datetime.now().isoformat()
                        state.error = "Server wird beendet, Simulation wurde abgebrochen"
                        cls._save_run_state(state)
                    
                    # Aktualisiere state.json und setze Status auf stopped
                    try:
                        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
                        state_file = os.path.join(sim_dir, "state.json")
                        logger.info(f"Versuche state.json zu aktualisieren: {state_file}")
                        if os.path.exists(state_file):
                            with open(state_file, 'r', encoding='utf-8') as f:
                                state_data = json.load(f)
                            state_data['status'] = 'stopped'
                            state_data['updated_at'] = datetime.now().isoformat()
                            with open(state_file, 'w', encoding='utf-8') as f:
                                json.dump(state_data, f, indent=2, ensure_ascii=False)
                            logger.info(f"state.json Status auf stopped aktualisiert: {simulation_id}")
                        else:
                            logger.warning(f"state.json existiert nicht: {state_file}")
                    except Exception as state_err:
                        logger.warning(f"state.json aktualisieren fehlgeschlagen: {simulation_id}, error={state_err}")
                        
            except Exception as e:
                logger.error(f"Prozess-Bereinigung fehlgeschlagen: {simulation_id}, error={e}")
        
        # Aufräumen der Dateihandles
        for simulation_id, file_handle in list(cls._stdout_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stdout_files.clear()
        
        for simulation_id, file_handle in list(cls._stderr_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stderr_files.clear()
        
        # Aufräumen des Zustands in der Arbeitsspeicher
        cls._processes.clear()
        cls._action_queues.clear()
        
        logger.info("Aufräumen der Simulationsprozesse abgeschlossen")
    
    @classmethod
    def register_cleanup(cls):
        """
        Registriere Bereinigungs-Funktionen
        
        Wird aufgerufen beim Start des Flask-Apps, um sicherzustellen, dass alle Prozesse bereinigt werden, wenn der Server heruntergefahren wird.
        """
        global _cleanup_registered
        
        if _cleanup_registered:
            return
        
        # Nur im reloader-Unterprozess registrieren, wenn Flask im Debugmodus läuft
        # WERKZEUG_RUN_MAIN=true bedeutet es ist der reloader-Unterprozess
        # Wenn nicht im Debugmodus, dann kein Umgebungsvariable und registrieren trotzdem
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_debug_mode = os.environ.get('FLASK_DEBUG') == '1' or os.environ.get('WERKZEUG_RUN_MAIN') is not None
        
        # Im Debugmodus nur im reloader-Unterprozess registrieren; außerhalb des Debugmodus immer registrieren
        if is_debug_mode and not is_reloader_process:
            _cleanup_registered = True  # Markiere als registriert, verhindere dass der Unterprozess es erneut versucht
            return
        
        # Speichere die ursprünglichen Signal-Handler
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        # SIGHUP existiert nur in Unix-Systemen (macOS/Linux), Windows hat es nicht
        original_sighup = None
        has_sighup = hasattr(signal, 'SIGHUP')
        if has_sighup:
            original_sighup = signal.getsignal(signal.SIGHUP)
        
        def cleanup_handler(signum=None, frame=None):
            """Signalhandler: Zuerst Aufräumen der Simulationsprozesse, dann Original-Handler aufrufen"""
            # Nur wenn Prozesse zum Aufräumen vorhanden sind, Protokolle drucken
            if cls._processes or cls._graph_memory_enabled:
                logger.info(f"Signal empfangen: {signum}, beginne Bereinigung...")
            cls.cleanup_all_simulations()
            
            # Rufe den ursprünglichen Signal-Handler auf, um Flask normal zu beenden
            if signum == signal.SIGINT and callable(original_sigint):
                original_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(original_sigterm):
                original_sigterm(signum, frame)
            elif has_sighup and signum == signal.SIGHUP:
                # SIGHUP: Sendiert wenn Terminal geschlossen wird
                if callable(original_sighup):
                    original_sighup(signum, frame)
                else:
                    # Standardverhalten: Normaler Beendigungsprozess
                    sys.exit(0)
            else:
                # Wenn der ursprüngliche Prozessor nicht aufrufbar ist (wie SIG_DFL), wird das Standardverhalten verwendet
                raise KeyboardInterrupt
        
        # Registriere atexit-Handler (als Backup)
        atexit.register(cls.cleanup_all_simulations)
        
        # Registriere Signalhandler (nur im Hauptthread)
        try:
            # SIGTERM: Standard-Signal für kill-Befehl
            signal.signal(signal.SIGTERM, cleanup_handler)
            # SIGINT: Ctrl+C
            signal.signal(signal.SIGINT, cleanup_handler)
            # SIGHUP: Terminal schließt (nur Unix-Systeme)
            if has_sighup:
                signal.signal(signal.SIGHUP, cleanup_handler)
        except ValueError:
            # Nicht im Hauptthread, nur atexit verwenden
            logger.warning("Kann Signalhandler nicht registrieren (nicht im Hauptthread), nutze nur atexit")
        
        _cleanup_registered = True
    
    @classmethod
    def get_running_simulations(cls) -> List[str]:
        """
        Erhalte die Liste aller laufenden Simulations-IDs
        """
        running = []
        for sim_id, process in cls._processes.items():
            if process.poll() is None:
                running.append(sim_id)
        return running
    
    # ============== Interview-Funktion ==============
    
    @classmethod
    def check_env_alive(cls, simulation_id: str) -> bool:
        """
        Prüfe, ob die Simulations-Umgebung aktiv ist (kann Interview-Befehle verarbeiten)

        Args:
            simulation_id: Simulations-ID

        Returns:
            True wenn die Umgebung aktiv ist, False wenn sie heruntergefahren wurde.
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        return ipc_client.check_env_alive()

    @classmethod
    def get_env_status_detail(cls, simulation_id: str) -> Dict[str, Any]:
        """
        Erhalte detaillierte Status-Informationen der Simulations-Umgebung

        Args:
            simulation_id: Simulations-ID

        Returns:
            Ein Dictionary mit den Details, einschließlich status, twitter_available, reddit_available, timestamp.
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        status_file = os.path.join(sim_dir, "env_status.json")
        
        default_status = {
            "status": "stopped",
            "twitter_available": False,
            "reddit_available": False,
            "timestamp": None
        }
        
        if not os.path.exists(status_file):
            return default_status
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return {
                "status": status.get("status", "stopped"),
                "twitter_available": status.get("twitter_available", False),
                "reddit_available": status.get("reddit_available", False),
                "timestamp": status.get("timestamp")
            }
        except (json.JSONDecodeError, OSError):
            return default_status

    @classmethod
    def interview_agent(
        cls,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """
        Führe ein Interview mit einem einzelnen Agent

        Args:
            simulation_id: Simulations-ID
            agent_id: Agent-ID
            prompt: Interview-Frage
            platform: Angegebene Plattform (optional)
                - "twitter": Nur Twitter-Plattform interviewen
                - "reddit": Nur Reddit-Plattform interviewen
                - None: Bei einer Doppelplattform simulieren, beide Platten gleichzeitig interviewen und kombinierte Ergebnisse zurückgeben.
            timeout: Timeout-Zeit (Sekunden)

        Returns:
            Ein Dictionary mit den Interview-Ergebnissen

        Raises:
            ValueError: Wenn die Simulation nicht existiert oder die Umgebung nicht läuft
            TimeoutError: Wenn das Antwort-Warten abläuft
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation existiert nicht: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"Simulationsumgebung nicht aktiv, Interview nicht möglich: {simulation_id}")

        logger.info(f"Interview-Befehl senden: simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}")

        response = ipc_client.send_interview(
            agent_id=agent_id,
            prompt=prompt,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "agent_id": agent_id,
                "prompt": prompt,
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "agent_id": agent_id,
                "prompt": prompt,
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Führe ein Batch-Interview mit mehreren Agents

        Args:
            simulation_id: Simulations-ID
            interviews: Interview-Liste, jedes Element enthält {"agent_id": int, "prompt": str, "platform": str(optional)}
            platform: Standardplattform (optional, wird von jeder Interview-Item-Plattform überschrieben)
                - "twitter": Nur Twitter-Plattform interviewen
                - "reddit": Nur Reddit-Plattform interviewen
                - None: Bei einer Doppelplattform simulieren, jedes Agent gleichzeitig beide Platten interviewen.
            timeout: Timeout-Zeit (Sekunden)

        Returns:
            Ein Dictionary mit den Batch-Interview-Ergebnissen

        Raises:
            ValueError: Wenn die Simulation nicht existiert oder die Umgebung nicht läuft
            TimeoutError: Wenn das Antwort-Warten abläuft
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation existiert nicht: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"Simulationsumgebung nicht aktiv, Interview nicht möglich: {simulation_id}")

        logger.info(f"Batch-Interview-Befehl senden: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}")

        response = ipc_client.send_batch_interview(
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_all_agents(
        cls,
        simulation_id: str,
        prompt: str,
        platform: str = None,
        timeout: float = 180.0
    ) -> Dict[str, Any]:
        """
        Führe ein globales Interview mit allen Agents

        Nutze die gleiche Frage für jedes Agent in der Simulation.

        Args:
            simulation_id: Simulations-ID
            prompt: Interview-Frage (gleich für alle Agents)
            platform: Angegebene Plattform (optional)
                - "twitter": Nur Twitter-Plattform interviewen
                - "reddit": Nur Reddit-Plattform interviewen
                - None: Bei einer Doppelplattform simulieren, jedes Agent gleichzeitig beide Platten interviewen.
            timeout: Timeout-Zeit (Sekunden)

        Returns:
            Ein Dictionary mit den Ergebnissen des globalen Interviews
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation existiert nicht: {simulation_id}")

        # Hole alle Agent-Informationen aus der Konfigurationsdatei
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if not os.path.exists(config_path):
            raise ValueError(f"Simulationskonfiguration existiert nicht: {simulation_id}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        if not agent_configs:
            raise ValueError(f"Keine Agents in Simulationskonfiguration: {simulation_id}")

        # Erstelle Liste für Batch-Interviews
        interviews = []
        for agent_config in agent_configs:
            agent_id = agent_config.get("agent_id")
            if agent_id is not None:
                interviews.append({
                    "agent_id": agent_id,
                    "prompt": prompt
                })

        logger.info(f"Globaler Interview-Befehl senden: simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}")

        return cls.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )
    
    @classmethod
    def close_simulation_env(
        cls,
        simulation_id: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Schließe die Simulations-Umgebung (und nicht den Prozess)
        
        Sendet der Simulation einen Befehl, um sie zu schließen und in einem wartenden Modus abzuschließen.
        
        Args:
            simulation_id: Simulations-ID
            timeout: Timeout-Zeit (Sekunden)
            
        Returns:
            Ein Dictionary mit den Ergebnissen der Operation
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"Simulation existiert nicht: {simulation_id}")
        
        ipc_client = SimulationIPCClient(sim_dir)
        
        if not ipc_client.check_env_alive():
            return {
                "success": True,
                "message": "Umgebung wurde beendet"
            }
        
        logger.info(f"Umgebung-schließen-Befehl senden: simulation_id={simulation_id}")
        
        try:
            response = ipc_client.send_close_env(timeout=timeout)
            
            return {
                "success": response.status.value == "completed",
                "message": "Befehl zur Beendigung der Umgebung wurde gesendet",
                "result": response.result,
                "timestamp": response.timestamp
            }
        except TimeoutError:
            # Timeout könnte aufgrund des Schließens der Umgebung auftreten
            return {
                "success": True,
                "message": "Befehl zur Beendigung der Umgebung wurde gesendet (Wartezeit für Antwort abgelaufen, Umgebung könnte sich gerade beenden)"
            }
    
    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Hole Interview-Historie aus einer einzelnen Datenbank"""
        import sqlite3
        
        if not os.path.exists(db_path):
            return []
        
        results = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if agent_id is not None:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview' AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (agent_id, limit))
            else:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            for user_id, info_json, created_at in cursor.fetchall():
                try:
                    info = json.loads(info_json) if info_json else {}
                except json.JSONDecodeError:
                    info = {"raw": info_json}
                
                results.append({
                    "agent_id": user_id,
                    "response": info.get("response", info),
                    "prompt": info.get("prompt", ""),
                    "timestamp": created_at,
                    "platform": platform_name
                })
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Interview-Verlauf lesen fehlgeschlagen ({platform_name}): {e}")
        
        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Erhalte die Interview-Historie (liest aus der Datenbank)
        
        Args:
            simulation_id: Simulations-ID
            platform: Plattform-Typ (reddit/twitter/None)
                - "reddit": Nur Reddit-Plattform historie
                - "twitter": Nur Twitter-Plattform historie
                - None: Historie von beiden Platten erhalten.
            agent_id: Angegebene Agent-ID (optional, nur die Historie dieses Agents erhalten)
            limit: Anzahl der Elemente pro Plattform begrenzen
            
        Returns:
            Eine Liste mit den Interview-Historien
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        results = []
        
        # Bestimme zu überprüfende Plattform
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # Ohne spezifizierte Plattform, überprüfe beide Plattformen
            platforms = ["twitter", "reddit"]
        
        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path,
                platform_name=p,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(platform_results)
        
        # Sortiere nach absteigender Zeit
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Wenn mehrere Plattformen überprüft werden, begrenze Gesamtzahl
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]
        
        return results

