"""
Zep-Graph-Memory-Update-Service
Agent-Aktivitäten aus der Simulation dynamisch in den Zep-Graphen übertragen
"""

import os
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale

logger = get_logger('mirofish.zep_graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent-Aktivitätseintrag"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str
    
    def to_episode_text(self) -> str:
        """
        Aktivität in Textbeschreibung für Zep konvertieren
        
        Natürlichsprachliches Format, damit Zep Entitäten und Beziehungen extrahieren kann.
        Kein Simulations-Präfix, um Graph-Updates nicht zu verfälschen.
        """
        # Je nach Aktionstyp unterschiedliche Beschreibung generieren
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }
        
        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()
        
        # Direkt "AgentName: Beschreibung" zurückgeben, ohne Simulations-Präfix
        return f"{self.agent_name}: {description}"
    
    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"hat einen Beitrag veröffentlicht: «{content}»"
        return "hat einen Beitrag veröffentlicht"
    
    def _describe_like_post(self) -> str:
        """Beitrag liken - mit Originaltext und Autoreninfo"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"hat den Beitrag von {post_author} geliked: «{post_content}»"
        elif post_content:
            return f"hat einen Beitrag geliked: «{post_content}»"
        elif post_author:
            return f"hat einen Beitrag von {post_author} geliked"
        return "hat einen Beitrag geliked"
    
    def _describe_dislike_post(self) -> str:
        """Beitrag disliken - mit Originaltext und Autoreninfo"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"hat den Beitrag von {post_author} gedisliked: «{post_content}»"
        elif post_content:
            return f"hat einen Beitrag gedisliked: «{post_content}»"
        elif post_author:
            return f"hat einen Beitrag von {post_author} gedisliked"
        return "hat einen Beitrag gedisliked"
    
    def _describe_repost(self) -> str:
        """Beitrag teilen - mit Originalinhalt und Autoreninfo"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        
        if original_content and original_author:
            return f"hat den Beitrag von {original_author} geteilt: «{original_content}»"
        elif original_content:
            return f"hat einen Beitrag geteilt: «{original_content}»"
        elif original_author:
            return f"hat einen Beitrag von {original_author} geteilt"
        return "hat einen Beitrag geteilt"
    
    def _describe_quote_post(self) -> str:
        """Beitrag zitieren - mit Originalinhalt, Autoreninfo und Zitat-Kommentar"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        
        base = ""
        if original_content and original_author:
            base = f"hat den Beitrag von {original_author} zitiert: «{original_content}»"
        elif original_content:
            base = f"hat einen Beitrag zitiert: «{original_content}»"
        elif original_author:
            base = f"hat einen Beitrag von {original_author} zitiert"
        else:
            base = "hat einen Beitrag zitiert"
        
        if quote_content:
            base += f" und kommentiert: «{quote_content}»"
        return base
    
    def _describe_follow(self) -> str:
        """Nutzer folgen - mit Name des gefolgten Nutzers"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"folgt jetzt dem Nutzer «{target_user_name}»"
        return "folgt jetzt einem Nutzer"
    
    def _describe_create_comment(self) -> str:
        """Kommentar erstellen - mit Kommentarinhalt und Beitragsinfo"""
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if content:
            if post_content and post_author:
                return f"hat den Beitrag «{post_content}» von {post_author} kommentiert: «{content}»"
            elif post_content:
                return f"hat den Beitrag «{post_content}» kommentiert: «{content}»"
            elif post_author:
                return f"hat den Beitrag von {post_author} kommentiert: «{content}»"
            return f"hat kommentiert: «{content}»"
        return "hat einen Kommentar verfasst"
    
    def _describe_like_comment(self) -> str:
        """Kommentar liken - mit Kommentarinhalt und Autoreninfo"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"hat den Kommentar von {comment_author} geliked: «{comment_content}»"
        elif comment_content:
            return f"hat einen Kommentar geliked: «{comment_content}»"
        elif comment_author:
            return f"hat einen Kommentar von {comment_author} geliked"
        return "hat einen Kommentar geliked"
    
    def _describe_dislike_comment(self) -> str:
        """Kommentar disliken - mit Kommentarinhalt und Autoreninfo"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"hat den Kommentar von {comment_author} gedisliked: «{comment_content}»"
        elif comment_content:
            return f"hat einen Kommentar gedisliked: «{comment_content}»"
        elif comment_author:
            return f"hat einen Kommentar von {comment_author} gedisliked"
        return "hat einen Kommentar gedisliked"
    
    def _describe_search(self) -> str:
        """Beiträge suchen - mit Suchbegriff"""
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"hat nach «{query}» gesucht" if query else "hat eine Suche durchgeführt"
    
    def _describe_search_user(self) -> str:
        """Nutzer suchen - mit Suchbegriff"""
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"hat nach Nutzer «{query}» gesucht" if query else "hat nach einem Nutzer gesucht"
    
    def _describe_mute(self) -> str:
        """Nutzer stummschalten - mit Name des stummgeschalteten Nutzers"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"hat den Nutzer «{target_user_name}» stummgeschaltet"
        return "hat einen Nutzer stummgeschaltet"
    
    def _describe_generic(self) -> str:
        # Für unbekannte Aktionstypen eine generische Beschreibung
        return f"hat die Aktion {self.action_type} ausgeführt"


class ZepGraphMemoryUpdater:
    """
    Zep-Graph-Memory-Updater
    
    Überwacht die Actions-Logdateien der Simulation und überträgt neue Agent-Aktivitäten
    in Echtzeit in den Zep-Graphen. Gruppiert nach Plattform, sendet nach BATCH_SIZE
    Aktivitäten gesammelt an Zep.
    
    Alle bedeutsamen Aktionen werden an Zep übertragen, action_args enthält vollständige
    Kontextinformationen:
    - Originaltext gelikter/gedislikter Beiträge
    - Originaltext geteilter/zitierter Beiträge
    - Name des gefolgten/stummgeschalteten Nutzers
    - Originaltext gelikter/gedislikter Kommentare
    """
    
    # Batch-Größe (pro Plattform, Anzahl vor Versand)
    BATCH_SIZE = 5
    
    # Plattform-Anzeigenamen (für Konsole)
    PLATFORM_DISPLAY_NAMES = {
        'twitter': 'Welt 1',
        'reddit': 'Welt 2',
    }
    
    # Sende-Intervall (Sekunden), um zu schnelle Requests zu vermeiden
    SEND_INTERVAL = 0.5
    
    # Retry-Konfiguration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # Sekunden
    
    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        """
        Updater initialisieren
        
        Args:
            graph_id: Zep-Graph-ID
            api_key: Zep API Key (optional, Standard aus Config)
        """
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY
        
        if not self.api_key:
            raise ValueError("ZEP_API_KEY nicht konfiguriert")
        
        self.client = Zep(api_key=self.api_key)
        
        # Aktivitäts-Queue
        self._activity_queue: Queue = Queue()
        
        # Plattform-gruppierte Aktivitätspuffer (jede Plattform akkumuliert bis BATCH_SIZE)
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()
        
        # Steuerungs-Flags
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # Statistik
        self._total_activities = 0  # Tatsächlich zur Queue hinzugefügte Aktivitäten
        self._total_sent = 0        # Erfolgreich an Zep gesendete Batches
        self._total_items_sent = 0  # Erfolgreich an Zep gesendete Aktivitäten
        self._failed_count = 0      # Fehlgeschlagene Batches
        self._skipped_count = 0     # Gefilterte/übersprungene Aktivitäten (DO_NOTHING)
        
        logger.info(f"ZepGraphMemoryUpdater initialisiert: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")
    
    def _get_platform_display_name(self, platform: str) -> str:
        """Anzeigename der Plattform abrufen"""
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)
    
    def start(self):
        """Hintergrund-Worker-Thread starten"""
        if self._running:
            return

        # Capture locale before spawning background thread
        current_locale = get_locale()

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(current_locale,),
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater gestartet: graph_id={self.graph_id}")
    
    def stop(self):
        """Hintergrund-Worker-Thread stoppen"""
        self._running = False
        
        # Verbleibende Aktivitäten senden
        self._flush_remaining()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        
        logger.info(f"ZepGraphMemoryUpdater gestoppt: graph_id={self.graph_id}, "
                   f"total_activities={self._total_activities}, "
                   f"batches_sent={self._total_sent}, "
                   f"items_sent={self._total_items_sent}, "
                   f"failed={self._failed_count}, "
                   f"skipped={self._skipped_count}")
    
    def add_activity(self, activity: AgentActivity):
        """
        Eine Agent-Aktivität zur Queue hinzufügen
        
        Alle bedeutsamen Aktionen werden zur Queue hinzugefügt:
        - CREATE_POST (Beitrag erstellen)
        - CREATE_COMMENT (Kommentar erstellen)
        - QUOTE_POST (Beitrag zitieren)
        - SEARCH_POSTS (Beiträge suchen)
        - SEARCH_USER (Nutzer suchen)
        - LIKE_POST/DISLIKE_POST (Beitrag liken/disliken)
        - REPOST (Teilen)
        - FOLLOW (Folgen)
        - MUTE (Stummschalten)
        - LIKE_COMMENT/DISLIKE_COMMENT (Kommentar liken/disliken)
        
        action_args enthält vollständige Kontextinfos (Beitragstext, Nutzernamen etc.).
        
        Args:
            activity: Agent-Aktivitätseintrag
        """
        # DO_NOTHING-Aktivitäten überspringen
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        
        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"Aktivität zur Zep-Queue hinzugefügt: {activity.agent_name} - {activity.action_type}")
    
    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """
        Aktivität aus Dictionary-Daten hinzufügen
        
        Args:
            data: Aus actions.jsonl geparste Dictionary-Daten
            platform: Plattformname (twitter/reddit)
        """
        # Event-Typ-Einträge überspringen
        if "event_type" in data:
            return
        
        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        
        self.add_activity(activity)
    
    def _worker_loop(self, locale: str = 'zh'):
        """Hintergrund-Arbeitsschleife - Aktivitäten plattformweise als Batch an Zep senden"""
        set_locale(locale)
        while self._running or not self._activity_queue.empty():
            try:
                # Aktivität aus Queue holen (Timeout 1 Sekunde)
                try:
                    activity = self._activity_queue.get(timeout=1)
                    
                    # Aktivität zum Plattform-Puffer hinzufügen
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)
                        
                        # Prüfen ob Batch-Größe erreicht
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            # Lock freigeben, dann senden
                            self._send_batch_activities(batch, platform)
                            # Sende-Intervall einhalten
                            time.sleep(self.SEND_INTERVAL)
                    
                except Empty:
                    pass
                    
            except Exception as e:
                logger.error(f"Fehler in Arbeitsschleife: {e}")
                time.sleep(1)
    
    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
        Aktivitäten als Batch an Zep-Graph senden (zusammengeführt als ein Text)
        
        Args:
            activities: Liste der Agent-Aktivitäten
            platform: Plattformname
        """
        if not activities:
            return
        
        # Mehrere Aktivitäten zu einem Text zusammenführen
        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)
        
        # Senden mit Retry
        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=combined_text
                )
                
                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"Batch mit {len(activities)} {display_name}-Aktivitäten erfolgreich an Graph {self.graph_id} gesendet")
                logger.debug(f"Batch-Vorschau: {combined_text[:200]}...")
                return
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Batch-Senden an Zep fehlgeschlagen (Versuch {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"Batch-Senden an Zep fehlgeschlagen nach {self.MAX_RETRIES} Versuchen: {e}")
                    self._failed_count += 1
    
    def _flush_remaining(self):
        """Verbleibende Aktivitäten aus Queue und Puffer senden"""
        # Zuerst Queue-Rest in Puffer übertragen
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break
        
        # Dann verbleibende Puffer-Aktivitäten senden (auch unter BATCH_SIZE)
        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"Sende verbleibende {len(buffer)} {display_name}-Aktivitäten")
                    self._send_batch_activities(buffer, platform)
            # Alle Puffer leeren
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiken abrufen"""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,  # Zur Queue hinzugefügte Aktivitäten
            "batches_sent": self._total_sent,            # Erfolgreich gesendete Batches
            "items_sent": self._total_items_sent,        # Erfolgreich gesendete Aktivitäten
            "failed_count": self._failed_count,          # Fehlgeschlagene Batches
            "skipped_count": self._skipped_count,        # Gefilterte Aktivitäten (DO_NOTHING)
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,                # Puffergrößen pro Plattform
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
    Verwaltet Zep-Graph-Memory-Updater für mehrere Simulationen
    
    Jede Simulation kann eine eigene Updater-Instanz haben
    """
    
    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()
    
    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
        Graph-Memory-Updater für Simulation erstellen
        
        Args:
            simulation_id: Simulations-ID
            graph_id: Zep-Graph-ID
            
        Returns:
            ZepGraphMemoryUpdater-Instanz
        """
        with cls._lock:
            # Falls bereits vorhanden, alten Updater stoppen
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            
            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            
            logger.info(f"Graph-Memory-Updater erstellt: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater
    
    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """Updater der Simulation abrufen"""
        return cls._updaters.get(simulation_id)
    
    @classmethod
    def stop_updater(cls, simulation_id: str):
        """Updater der Simulation stoppen und entfernen"""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"Graph-Memory-Updater gestoppt: simulation_id={simulation_id}")
    
    # Flag um doppelte stop_all-Aufrufe zu verhindern
    _stop_all_done = False
    
    @classmethod
    def stop_all(cls):
        """Alle Updater stoppen"""
        # Doppelaufruf verhindern
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        
        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"Updater stoppen fehlgeschlagen: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("Alle Graph-Memory-Updater gestoppt")
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Statistiken aller Updater abrufen"""
        return {
            sim_id: updater.get_stats() 
            for sim_id, updater in cls._updaters.items()
        }
