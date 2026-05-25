"""
Modul für interprozessige Kommunikation (IPC) in der Simulation
Verwendet zur Kommunikation zwischen dem Flask-Backend und den Simulations-Skripten.

Realisiert eine einfache Befehls-/Antwort-Methode über das Dateisystem:
1. Flask schreibt Befehle in den commands/-Ordner
2. Die Simulations-Skripte durchsuchen den Befehlsordner, führen die Befehle aus und schreiben Antworten in den responses/-Ordner.
3. Flask durchsucht den Antwort-Ordner, um Ergebnisse zu erhalten."""

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger('mirofish.simulation_ipc')


class CommandType(str, Enum):
    """Befehl-Typ"""
    INTERVIEW = "interview"           # Einzelne Agent-Interview
    BATCH_INTERVIEW = "batch_interview"  # Masseninterviews
    CLOSE_ENV = "close_env"           # Schließe Umgebung


class CommandStatus(str, Enum):
    """Befehls-Status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    """IPC-Befehl"""
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCCommand':
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class IPCResponse:
    """IPC-Antwort"""
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCResponse':
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class SimulationIPCClient:
    """
Intelligenter IPC-Klient (für die Verwendung im Flask-Backend)
Verwendet zur Sendung von Befehlen an den Simulationsprozess und zum Warten auf Antworten."""
    
    def __init__(self, simulation_dir: str):
        """
Initialisiert den IPC-Klienten.

Args:
            simulation_dir: Ordner für die Simulationsdaten"""
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # Stelle sicher, dass der Ordner existiert
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> IPCResponse:
        """
Sendet einen Befehl und wartet auf eine Antwort.

Args:
            command_type: Typ des Befehls
            args: Parameter für den Befehl
            timeout: Timeout (in Sekunden)
            poll_interval: Abfrageintervall (in Sekunden)

Returns:
            IPCResponse

Raises:
            TimeoutError: Warten auf Antwort überschreitet die Zeit."""
        command_id = str(uuid.uuid4())
        command = IPCCommand(
            command_id=command_id,
            command_type=command_type,
            args=args
        )
        
        # Schreibe Befehlsdatei
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"IPC-Befehl senden: {command_type.value}, command_id={command_id}")
        
        # Warte auf Antwort
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                    response = IPCResponse.from_dict(response_data)
                    
                    # Aufräumen von Befehl und Antwortdateien
                    try:
                        os.remove(command_file)
                        os.remove(response_file)
                    except OSError:
                        pass
                    
                    logger.info(f"IPC-Antwort empfangen: command_id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Antwort parsen fehlgeschlagen: {e}")
            
            time.sleep(poll_interval)
        
        # Zeitüberschreitung
        logger.error(f"Timeout bei IPC-Antwort: command_id={command_id}")
        
        # Aufräumen der Befehlsdatei
        try:
            os.remove(command_file)
        except OSError:
            pass
        
        raise TimeoutError(f"Timeout beim Warten auf Befehlsantwort ({timeout} Sek.)")
    
    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> IPCResponse:
        """
Sendet einen einzelnen Agent-Interview-Befehl.

Args:
            agent_id: ID des Agents
            prompt: Interviewfrage
            platform: Angegebene Plattform (optional)
                - "twitter": Nur Twitter-Plattform interviewen
                - "reddit": Nur Reddit-Plattform interviewen  
                - None: Bei dual-plattform-simulationen beide Platten interviewen, bei single-plattform-simulationen nur die angegebene Plattform interviewen.
            timeout: Timeout (in Sekunden)

Returns:
            IPCResponse, result-Feld enthält das Interviewergebnis."""
        args = {
            "agent_id": agent_id,
            "prompt": prompt
        }
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> IPCResponse:
        """
        Send batch interview commands
        
        Args:
            interviews: Interview list, each element contains {"agent_id": int, "prompt": str, "platform": str (optional)}
            platform: Default platform (optional, will be overridden by the platform of each interview item)
                - "twitter": Only interview Twitter platform
                - "reddit": Only interview Reddit platform
                - None: Simulate both platforms simultaneously for each Agent
            timeout: Timeout period
        
        Returns:
            IPCResponse, result field contains all interview results
        """
        args = {"interviews": interviews}
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.BATCH_INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        """
        Send command to close environment
        
        Args:
            timeout: Timeout period
        
        Returns:
            IPCResponse
        """
        return self.send_command(
            command_type=CommandType.CLOSE_ENV,
            args={},
            timeout=timeout
        )
    
    def check_env_alive(self) -> bool:
        """
        Check if the simulation environment is alive
        
        Determine by checking the env_status.json file
        """
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return status.get("status") == "alive"
        except (json.JSONDecodeError, OSError):
            return False


class SimulationIPCServer:
    """
    Simulation IPC server (used in simulation scripts)
    
    Poll the command directory, execute commands and return responses
    """
    
    def __init__(self, simulation_dir: str):
        """
        Initialize IPC server
        
        Args:
            simulation_dir: Directory for simulation data
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # Stelle sicher, dass der Ordner existiert
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        
        # Umgebungszustand
        self._running = False
    
    def start(self):
        """Markiere Server als laufend"""
        self._running = True
        self._update_env_status("alive")
    
    def stop(self):
        """Markiere Server als gestoppt"""
        self._running = False
        self._update_env_status("stopped")
    
    def _update_env_status(self, status: str):
        """Aktualisiere Umgebungsstatus-Datei"""
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_commands(self) -> Optional[IPCCommand]:
        """
        Poll the command directory and return the first pending command
        
        Returns:
            IPCCommand or None
        """
        if not os.path.exists(self.commands_dir):
            return None
        
        # Hole Befehlsdateien nach Zeit
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return IPCCommand.from_dict(data)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Befehlsdatei lesen fehlgeschlagen: {filepath}, {e}")
                continue
        
        return None
    
    def send_response(self, response: IPCResponse):
        """
        Send response
        
        Args:
            response: IPCResponse
        """
        response_file = os.path.join(self.responses_dir, f"{response.command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Befehlsdatei löschen
        command_file = os.path.join(self.commands_dir, f"{response.command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    def send_success(self, command_id: str, result: Dict[str, Any]):
        """Senden Sie erfolgreiche Antwort"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.COMPLETED,
            result=result
        ))
    
    def send_error(self, command_id: str, error: str):
        """Senden Sie Fehlerantwort"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.FAILED,
            error=error
        ))
