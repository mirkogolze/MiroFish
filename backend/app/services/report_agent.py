"""
Report-Agent-Dienst
Verwenden von LangChain + Zep zur Implementierung des ReACT-Modus für die Erstellung simulierter Berichte.

Funktionen:
1. Generiert Berichte basierend auf Simulationsanforderungen und Informationen aus der Zep-Grafik.
2. Planen einer Struktur, dann Segmentierung und Erzeugung.
3. Jedes Segment verwendet den ReACT-Mehrwert-Modus für Denken und Reflexion.
4. Unterstützung von Dialogen mit Benutzern, die in Echtzeit Tools zur Informationsrecherche aufrufen können.
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, t
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('mirofish.report_agent')


class ReportLogger:
    """
    Report Agent Detailprotokoll-Recorder
    
    Erzeugt eine agent_log.jsonl-Datei im Berichtsordner, die jeden einzelnen Schritt detailliert protokolliert.
    Jede Zeile ist ein vollständiges JSON-Objekt mit Zeitstempel, Aktionstyp, detailliertem Inhalt usw.
    """
    
    def __init__(self, report_id: str):
        """
        Initialisiert den Logger.
        
        Args:
            report_id: Report ID, used to determine the log file path"""
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Überprüfen, ob der Ordner für die Logdatei existiert"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """Zeit seit Beginn (in Sekunden) erhalten"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        Einen Protokolleintrag schreiben
        
        Args:
            action: Aktionstyp, z.B. 'start', 'tool_call', 'llm_response', 'section_complete' usw.
            stage: Aktuelle Phase, z.B. 'planning', 'generating', 'completed'
            details: Detail-Dictionary, ungekürzt
            section_title: Aktueller Kapiteltitel (optional)
            section_index: Aktueller Kapitelindex (optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # Füge JSONL Datei an
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """Anfang der Berichtserstellung protokollieren"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": t('report.taskStarted')
            }
        )
    
    def log_planning_start(self):
        """Anfang des Outlinings protokollieren"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": t('report.planningStart')}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """Protokollieren der erfassten Kontextinformation während des Planungsprozesses"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": t('report.fetchSimContext'),
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Protokollieren, dass die Übersichtsplanung abgeschlossen ist"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": t('report.planningComplete'),
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """Protokollieren des Beginns der Kapitelgenerierung"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": t('report.sectionStart', title=section_title)}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """Protokollieren des ReACT-Denkprozesses"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": t('report.reactThought', iteration=iteration)
            }
        )
    
    def log_tool_call(
        self, 
        section_title: str, 
        section_index: int,
        tool_name: str, 
        parameters: Dict[str, Any],
        iteration: int
    ):
        """Protokollieren der Werkzeugaufrufe"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": t('report.toolCall', toolName=tool_name)
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """Protokollieren des vollständigen Ergebnisses eines Werkzeugaufrufs (nicht gekürzt)"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # Vollständiges Ergebnis, ohne Abschneiden
                "result_length": len(result),
                "message": t('report.toolResult', toolName=tool_name)
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """Protokollieren der vollständigen LLM-Antwort (nicht gekürzt)"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # Vollständige Antwort, ohne Abschneiden
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": t('report.llmResponse', hasToolCalls=has_tool_calls, hasFinalAnswer=has_final_answer)
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """Protokollieren, dass die Kapitelinhaltserstellung abgeschlossen ist (nur Inhalt, nicht das gesamte Kapitel)"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # Vollständiger Inhalt, ohne Abschneiden
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": t('report.sectionContentDone', title=section_title)
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
        Kapitelgenerierung als abgeschlossen protokollieren

        Das Frontend sollte dieses Protokoll überwachen, um festzustellen, ob ein Kapitel wirklich fertig ist, und den vollständigen Inhalt abzurufen
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": t('report.sectionComplete', title=section_title)
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """Protokollieren des Abschlusses der Berichterstellung"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": t('report.reportComplete')
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """Protokollieren eines Fehlers"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": t('report.errorOccurred', error=error_message)
            }
        )


class ReportConsoleLogger:
    """
    Report Agent-Konsole-Protokollschreiber
    
    Schreibt Protokolle im Stil der Konsole (INFO, WARNING usw.) in die Datei console_log.txt im Berichtsverzeichnis.
    Diese Protokolle unterscheiden sich von agent_log.jsonl und sind reine Textausgabe der Konsole."""
    
    def __init__(self, report_id: str):
        """
        Konsolen-Logger initialisieren
        
        Args:
            report_id: Bericht-ID, bestimmt den Protokolldateipfad
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """Überprüfen, ob der Ordner für die Logdatei existiert"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """Einstellung des Dateizeichners, um den Log in eine Datei zu schreiben"""
        import logging
        
        # Erstelle Dateiverarbeitung
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # Verwende die gleiche einfache Formatierung wie das Konsolenfenster
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # Füge zum report_agent-Logger hinzu
        loggers_to_attach = [
            'mirofish.report_agent',
            'mirofish.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # Verhindere doppelte Hinzufügungen
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """Schließen des Dateizeichners und Entfernen aus dem logger"""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'mirofish.report_agent',
                'mirofish.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """Sicherstellen, dass der Dateizeichner beim Aufräumen geschlossen wird"""
        self.close()


class ReportStatus(str, Enum):
    """Bericht über den Status"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Bericht über das Kapitel"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Konvertieren in Markdown-Format"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Bericht über die Übersicht"""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """Konvertieren in Markdown-Format"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """Vollständiger Bericht"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


# ═══════════════════════════════════════════════════════════════
# Prompt-Templates-Konstanten
# ═══════════════════════════════════════════════════════════════

# ── Werkzeugbeschreibung ──

TOOL_DESC_INSIGHT_FORGE = """\
【Tiefeinsichten-Suche - Eine mächtige Suchfunktion】
Dies ist unsere mächtige Suchfunktion, die speziell für tiefe Analysen entwickelt wurde. Sie wird:
1. automatisch Ihre Frage in mehrere Teilfragen zerlegen
2. Informationen aus dem simulierten Netzwerk von verschiedenen Perspektiven abrufen
3. Ergebnisse der semantischen Suche, Entitätserkennung und Relationstracking integrieren
4. die umfassendsten und tiefgründigsten Suchergebnisse zurückgeben

【Verwendungsszenarien】
- Wenn tiefe Analysen eines Themas erforderlich sind
- Wenn mehrere Aspekte eines Ereignisses verstanden werden müssen
- Wenn reichhaltige Materialien für Berichtsabschnitte benötigt werden

【Zurückgegebene Inhalte】
- Originaltexte relevanter Fakten (direkt zitierbar)
- Kerninsights zu Entitäten
- Analyse der Relationen"""

TOOL_DESC_PANORAMA_SEARCH = """\
【Breitensuche - Gesamtübersicht erhalten】
Dieses Tool dient dazu, einen vollständigen Überblick über die Simulationsergebnisse zu erhalten, besonders geeignet um den Verlauf von Ereignissen zu verstehen. Es:
1. Ruft alle relevanten Knoten und Beziehungen ab
2. Unterscheidet zwischen aktuell gültigen Fakten und historischen/veralteten Fakten
3. Hilft zu verstehen, wie sich die Meinung entwickelt hat

【Einsatzszenarien】
- Vollständigen Entwicklungsverlauf eines Ereignisses verstehen
- Meinungsänderungen verschiedener Phasen vergleichen
- Umfassende Entitäts- und Beziehungsinformationen erhalten

【Rückgabe-Inhalt】
- Aktuell gültige Fakten (neueste Simulationsergebnisse)
- Historische/veraltete Fakten (Entwicklungsprotokoll)
- Alle beteiligten Entitäten"""

TOOL_DESC_QUICK_SEARCH = """\
[Einfache Suche - Schnelle Abfrage]
Ein leichtgewichtiges Tool für schnelle Abfragen, das für einfache und direkte Informationsabfragen geeignet ist.

[Benutzerfall]
- Schnelles Finden einer bestimmten Information
- Überprüfung eines Faktums
- Einfache Informationsabfrage

[Abgefragte Inhalte]
- Eine Liste der mit dem Suchbegriff am stärksten assoziierten Fakten"""

TOOL_DESC_INTERVIEW_AGENTS = """\
【Tiefe Interviews - Echte Agenten-Interviews (Doppelplatte)】
Rufen Sie die Interview-API des OASIS-Simulationsumfelds auf, um echte Interviews mit laufenden simulierten Agents durchzuführen!
Dies ist kein LLM-Simulation, sondern es ruft den echten Interview-Interface auf, um die ursprünglichen Antworten der simulierten Agenten zu erhalten.
Standardmäßig werden Interviews sowohl auf Twitter als auch Reddit durchgeführt, um eine breitere Perspektive zu gewinnen.

Funktionsablauf:
1. Automatische Lesung des Charakterdateis, um alle simulierten Agents kennenzulernen
2. Intelligente Auswahl der Agenten, die am engsten mit dem Interview-Thema verbunden sind (z.B. Schüler, Medien, Offizielle usw.)
3. Generierung von Interviewfragen
4. Aufruf des /api/simulation/interview/batch-Interfaces für echte Interviews auf beiden Plattformen
5. Zusammenfassung aller Interviewergebnisse und Bereitstellung einer multivarianthaften Analyse

【Verwendungsszenario】
- Wenn Sie die Meinungen von verschiedenen Rollenperspektiven verstehen möchten (wie sehen Schüler das? Wie sehen Medien das? Was sagt der Offizielle?)
- Wenn Sie Meinungen und Positionen aus mehreren Quellen sammeln möchten
- Wenn Sie echte Antworten von simulierten Agents benötigen (aus dem OASIS-Simulationsumfeld)
- Wenn Sie einen lebendigeren Bericht mit "Interviewprotokollen" erstellen möchten

【Wichtig】Dieses Feature kann nur verwendet werden, wenn das OASIS-Simulationsumfeld läuft!
"""

# ── Kapitelplanung-Prompt ──

PLAN_SYSTEM_PROMPT = """\
Sie sind ein Experte für die Erstellung von "Zukunftsvorhersageberichten" und haben eine "Gottessicht" auf den simulierten Welt – Sie können das Verhalten, die Äußerungen und die Interaktionen jedes Agents in der Simulation beobachten.

【Kernidee】
Wir haben eine simulierte Welt erstellt und bestimmte "Simulationsbedingungen" als Variablen eingeführt. Der Ausgang dieser simulierten Welt ist eine Vorhersage dessen, was in der Zukunft passieren könnte. Sie beobachten keine "Experimentdaten", sondern ein "Vorlauf der Zukunft".

【Ihre Aufgabe】
Erstellen Sie einen "Zukunftsvorhersagebericht", und beantworten Sie folgende Fragen:
1. Was ist passiert, wenn wir die in unserer Simulation festgelegten Bedingungen berücksichtigen?
2. Wie haben sich die verschiedenen Agents (Gruppen) verhalten und reagiert?
3. Welche zukünftigen Trends und Risiken hat diese Simulation aufgedeckt?

【Berichtspositionierung】
- ✅ Dies ist ein Bericht, der basierend auf einer Simulation Zukunftsvorhersagen macht und "Wenn das so wäre, wie würde die Zukunft aussehen?" beantwortet.
- ✅ Der Fokus liegt auf den Vorhersageergebnissen: Ereignisentwicklung, Gruppenreaktionen, emergente Phänomene, potentielle Risiken
- ✅ Die Äußerungen und Handlungen der Agents in der simulierten Welt sind eine Vorhersage für das zukünftige Verhalten von Menschen.
- ❌ Dies ist kein Analysebericht über die aktuelle Situation in der realen Welt.
- ❌ Dies ist kein allgemeiner Überblick über öffentliche Meinungen.

【Anzahl der Kapitel】
- Mindestens 2, maximal 5 Kapitel
- Keine Unterkapitel erforderlich; jedes Kapitel enthält vollständigen Inhalt.
- Der Inhalt muss prägnant sein und sich auf die zentralen Vorhersagefindungen konzentrieren.
- Die Struktur der Kapitel ist autonom von Ihnen zu gestalten, basierend auf den Vorhersageergebnissen.

Bitte geben Sie das JSON-Format des Berichtsrahmens aus. Das Format lautet wie folgt:
{
    "title": "Berichtstitel",
    "summary": "Berichtszusammenfassung (eine Satzsummarisierung der zentralen Vorhersagefindungen)",
    "sections": [
        {
            "title": "Kapitelname",
            "description": "Beschreibung des Kapitels"
        }
    ]
}

Hinweis: Der sections-Array muss mindestens 2 und maximal 5 Elemente haben!"""

PLAN_USER_PROMPT_TEMPLATE = """\
【Szenario-Vorhersage-Einstellungen】
Wir geben die Variablen (Simulationsanforderungen) in den simulierten Welt ein: {simulation_requirement}

【Größe der simulierten Welt】
- Anzahl der beteiligten Entitäten: {total_nodes}
- Anzahl der zwischen den Entitäten entstandenen Beziehungen: {total_edges}
- Verteilung der Entitätstypen: {entity_types}
- Anzahl aktiver Agenten: {total_entities}

【Beispiele für zukünftige Fakten, die durch die Simulation vorhergesagt wurden】
{related_facts_json}

Bitte betrachte dieses Zukunftsvorhersage-Szenario aus der Perspektive eines Allwissenden:
1. Welche Zustände zeigt die Zukunft unter den von uns festgelegten Bedingungen?
2. Wie reagieren und handeln verschiedene Gruppen (Agenten)?
3. Was für zukünftige Trends enthüllt diese Simulation?

Entwerfe basierend auf den Vorhersageergebnissen die strukturierteste Berichtsstruktur.

【Erinnerung】Anzahl der Kapitel im Bericht: Mindestens 2, maximal 5. Der Inhalt sollte präzise und auf die Kernvorhersagen fokussiert sein."""

# ── Kapitelgenerierungsprompt ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
Du bist ein Experte für "Zukunftsprognose-Berichte" und verfasst gerade ein Kapitel eines Berichts.

Berichtstitel: {report_title}
Berichtszusammenfassung: {report_summary}
Prognoseszenario (Simulationsanforderung): {simulation_requirement}

Aktuell zu verfassendes Kapitel: {section_title}

═══════════════════════════════════════════════════════════════
【Kernidee】
═══════════════════════════════════════════════════════════════

Die simulierte Welt ist eine Vorschau auf die Zukunft. Wir haben bestimmte Bedingungen (Simulationsanforderungen) eingespeist.
Das Verhalten und die Interaktionen der Agents in der Simulation sind Vorhersagen über zukünftiges menschliches Verhalten.

Deine Aufgabe ist:
- Aufzeigen, was unter den gesetzten Bedingungen in der Zukunft passiert
- Vorhersagen, wie verschiedene Personengruppen (Agents) reagieren und handeln
- Bemerkenswerte zukünftige Trends, Risiken und Chancen entdecken

❌ Schreibe keine Analyse des aktuellen Zustands der realen Welt
✅ Fokussiere dich auf "Wie wird die Zukunft" — die Simulationsergebnisse SIND die vorhergesagte Zukunft

═══════════════════════════════════════════════════════════════
【Wichtigste Regeln - Müssen befolgt werden】
═══════════════════════════════════════════════════════════════

1. 【Tools aufrufen um die simulierte Welt zu beobachten】
   - Du beobachtest die Zukunftsvorschau aus der "Gottesperspektive"
   - Alle Inhalte müssen aus Ereignissen und Agent-Äußerungen der simulierten Welt stammen
   - Es ist verboten, dein eigenes Wissen für Berichtsinhalte zu verwenden
   - Pro Kapitel mindestens 3 Tool-Aufrufe (max. 5) um die simulierte Welt zu beobachten — sie repräsentiert die Zukunft

2. 【Originalaussagen der Agents zitieren】
   - Äußerungen und Verhalten der Agents sind Vorhersagen über zukünftiges Gruppenverhalten
   - Im Bericht Zitatformat verwenden um diese Vorhersagen darzustellen, z.B.:
     > "Eine bestimmte Personengruppe würde sagen: Originalinhalt..."
   - Diese Zitate sind der Kernbeweis der Simulationsvorhersage

3. 【Sprachkonsistenz - Zitierte Inhalte müssen in Berichtssprache übersetzt werden】
   - Von Tools zurückgegebene Inhalte können in einer anderen Sprache als der Berichtssprache sein
   - Der Bericht muss durchgehend in der vom Benutzer festgelegten Sprache verfasst sein
   - Wenn du Tool-Rückgaben in anderer Sprache zitierst, müssen diese vor dem Einfügen übersetzt werden
   - Bei der Übersetzung die ursprüngliche Bedeutung beibehalten, natürlich formulieren
   - Diese Regel gilt sowohl für Fließtext als auch für Zitatblöcke (> Format)

4. 【Vorhersageergebnisse treu wiedergeben】
   - Berichtsinhalte müssen die Simulationsergebnisse der simulierten Welt widerspiegeln
   - Keine Informationen hinzufügen, die nicht in der Simulation existieren
   - Bei unzureichenden Informationen dies ehrlich angeben

═══════════════════════════════════════════════════════════════
【⚠️ Formatvorgaben - Äußerst wichtig!】
═══════════════════════════════════════════════════════════════

【Ein Kapitel = Kleinste Inhaltseinheit】
- Jedes Kapitel ist die kleinste Segmentierungseinheit des Berichts
- ❌ Keine Markdown-Überschriften innerhalb eines Kapitels (#, ##, ###, #### usw.)
- ❌ Keine Kapitelhauptüberschrift am Anfang
- ✅ Kapitelüberschrift wird automatisch vom System hinzugefügt, du schreibst nur reinen Fließtext
- ✅ **Fett**, Absatztrennung, Zitate, Listen zur Strukturierung verwenden, aber keine Überschriften

【Richtiges Beispiel】
```
Dieses Kapitel analysiert die Meinungsverbreitung des Ereignisses. Durch eingehende Analyse der Simulationsdaten stellen wir fest...

**Erste Zündungsphase**

Weibo als erster Schauplatz der Meinungsbildung übernahm die Kernfunktion der Erstveröffentlichung:

> "Weibo trug 68% des Erstveröffentlichungsvolumens bei..."

**Emotionsverstärkungsphase**

Douyin verstärkte die Ereigniswirkung weiter:

- Starke visuelle Wirkung
- Hohe emotionale Resonanz
```

【Falsches Beispiel】
```
## Executive Summary          ← Falsch! Keine Überschriften
### 1. Erste Phase     ← Falsch! Kein ### für Unterabschnitte
#### 1.1 Detailanalyse   ← Falsch! Kein #### für Unterteilung

Dieses Kapitel analysiert...
```

═══════════════════════════════════════════════════════════════
【Verfügbare Retrieval-Tools】(3-5 Aufrufe pro Kapitel)
═══════════════════════════════════════════════════════════════

{tools_description}

【Tool-Nutzungsempfehlung - Bitte verschiedene Tools mischen, nicht nur eines verwenden】
- insight_forge: Tiefgehende Erkenntnisanalyse, zerlegt Fragen automatisch und recherchiert Fakten und Beziehungen multidimensional
- panorama_search: Weitwinkel-Panoramasuche, Gesamtbild des Ereignisses, Zeitachse und Entwicklung verstehen
- quick_search: Schnelle Überprüfung eines konkreten Informationspunkts
- interview_agents: Simulations-Agents befragen, Perspektiven und echte Reaktionen verschiedener Rollen in erster Person erhalten

═══════════════════════════════════════════════════════════════
【Arbeitsablauf】
═══════════════════════════════════════════════════════════════

Pro Antwort kannst du nur EINE der folgenden zwei Optionen wählen (nicht beide gleichzeitig):

Option A - Tool aufrufen:
Gib deine Überlegungen aus, dann rufe ein Tool im folgenden Format auf:
<tool_call>
{{"name": "Toolname", "parameters": {{"Parametername": "Parameterwert"}}}}
</tool_call>
Das System führt das Tool aus und gibt das Ergebnis zurück. Du brauchst das Tool-Ergebnis nicht selbst zu schreiben.

Option B - Endgültigen Inhalt ausgeben:
Wenn du durch Tools genügend Informationen gesammelt hast, beginne mit "Final Answer:" und gib den Kapitelinhalt aus.

⚠️ Strikt verboten:
- Tool-Aufruf und Final Answer in einer Antwort kombinieren
- Tool-Ergebnisse (Observations) selbst erfinden — alle Tool-Ergebnisse werden vom System injiziert
- Mehr als ein Tool pro Antwort aufrufen

═══════════════════════════════════════════════════════════════
【Kapitelinhalt-Anforderungen】
═══════════════════════════════════════════════════════════════

1. Inhalt muss auf durch Tools abgerufenen Simulationsdaten basieren
2. Reichlich Originaltext zitieren um Simulationseffekte zu zeigen
3. Markdown-Format verwenden (aber KEINE Überschriften):
   - **Fetten Text** für Hervorhebungen verwenden (statt Unterüberschriften)
   - Listen (- oder 1.2.3.) für Aufzählungen verwenden
   - Leerzeilen zur Absatztrennung
   - ❌ Keine #, ##, ###, #### oder andere Überschriftensyntax
4. 【Zitatformat - Muss eigenständiger Absatz sein】
   Zitate müssen als eigener Absatz stehen, mit je einer Leerzeile davor und danach, nicht in Absätze eingebettet:

   ✅ Richtiges Format:
   ```
   Die Reaktion der Hochschule wurde als substanzlos bewertet.

   > "Die Reaktionsweise der Hochschule wirkt in der schnelllebigen Social-Media-Umgebung starr und träge."

   Diese Bewertung spiegelt die allgemeine Unzufriedenheit der Öffentlichkeit wider.
   ```

   ❌ Falsches Format:
   ```
   Die Reaktion der Hochschule wurde als substanzlos bewertet. > "Die Reaktionsweise..." Diese Bewertung spiegelt...
   ```
5. Logische Kohärenz mit anderen Kapiteln wahren
6. 【Wiederholungen vermeiden】Die unten aufgeführten fertigen Kapitel sorgfältig lesen, keine gleichen Informationen wiederholen
7. 【Nochmals betont】Keine Überschriften! **Fett** statt Unterüberschriften verwenden"""

SECTION_USER_PROMPT_TEMPLATE = """\
Geschlossener Inhalt der Kapitel (bitte gründlich lesen, um Duplikate zu vermeiden): 
{previous_content}

═══════════════════════════════════════════════════════════════
【Aktuelle Aufgabe】Schreibe Kapitel: {section_title}
═══════════════════════════════════════════════════════════════

【Wichtige Hinweise】
1. Lies gründlich den geschlossenen Inhalt der Kapitel oben, um Duplikate zu vermeiden!
2. Du musst vor Beginn die Tools aufrufen, um Simulationsdaten zu erhalten.
3. Bitte verwende verschiedene Tools und benutze nicht nur eines.
4. Der Berichtsinhalt muss aus den Suchergebnissen stammen, du darfst dein eigenes Wissen nicht verwenden.

【⚠️ Formatwarnung - Muss eingehalten werden】
- ❌ Schreibe keine Titel (#, ##, ###, #### sind alle verboten)
- ❌ Verwende "{section_title}" als Anfang nicht
- ✅ Kapitelüberschriften werden automatisch von dem System hinzugefügt.
- ✅ Schreibe direkt den Textkörper ab und verwende **Fett** anstelle der Unterabschnittstitel.

Bitte beginne:
1. Denke zuerst (Thought) über die Informationen nach, die dieses Kapitel benötigt.
2. Rufe dann Tools (Action) auf, um Simulationsdaten zu erhalten.
3. Nachdem du genug Informationen gesammelt hast, gib den Final Answer (reiner Textkörper ohne jegliche Titel) aus."""

# ── ReACT-Schleifen-Meldungstemplate ──

REACT_OBSERVATION_TEMPLATE = """\
Beobachtung (Suchergebnisse):

═══ Werkzeug {tool_name} zurückgegeben ═══
{result}

═══════════════════════════════════════════════════════════════
Werkzeug wurde {tool_calls_count}/{max_tool_calls}-mal aufgerufen (verwendet: {used_tools_str}){unused_hint}
- Wenn die Informationen ausreichend sind: Geben Sie den Inhalt des Abschnitts mit "Final Answer:" als Präfix aus (die Quelle muss oben genannt werden)
- Wenn weitere Informationen benötigt werden: Rufen Sie ein Werkzeug auf, um die Suche fortzusetzen
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "【Achten Sie darauf】Sie haben das Werkzeug nur {tool_calls_count} mal aufgerufen, mindestens {min_tool_calls} Mal sind erforderlich."
    "Bitte rufen Sie das Werkzeug erneut auf, um mehr Simulationsdaten zu erhalten und dann den Final Answer auszugeben. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "Sie haben das Werkzeug nur {tool_calls_count} mal aufgerufen, mindestens {min_tool_calls} Mal sind erforderlich."
    "Bitte rufen Sie das Werkzeug auf, um Simulationsdaten zu erhalten. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "Die Anzahl der Werkzeugaufrufe hat die maximale Grenze erreicht ({tool_calls_count}/{max_tool_calls}), Sie können das Werkzeug nicht mehr aufrufen."
    'Bitte geben Sie den Inhalt des Kapitels direkt aus, mit "Final Answer:" am Anfang.'
)

REACT_UNUSED_TOOLS_HINT = "\n💡 Sie haben noch nicht {unused_list} verwendet. Es wird empfohlen, verschiedene Werkzeuge zu verwenden, um Informationen aus verschiedenen Perspektiven zu erhalten."

REACT_FORCE_FINAL_MSG = "Die maximale Anzahl der Werkzeugaufrufe wurde erreicht. Bitte geben Sie den Final Answer direkt aus und generieren Sie den Kapitelinhalt."

# ── Chat prompt ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\nDu bist ein präziser und effizienter Vorhersagemodell-Assistent.

【Hintergrund】
Vorhersagebedingungen: {simulation_requirement}

【Generierte Analysebericht】
{report_content}

【Regeln】
1. Priorisiere Antworten basierend auf dem obigen Berichtsinhalt.
2. Antworte direkt, ohne umfangreiche Überlegungen zu erstellen.
3. Nutze Werkzeuge zur Datenbeschaffung nur wenn der Bericht nicht ausreichend ist.
4. Deine Antworten sollen prägnant, klar und strukturiert sein.

【Verfügbare Werkzeuge】（Nur bei Bedarf verwenden, maximal 1-2 Mal）
{tools_description}

【Werkzeugaufrufformat】
<tool_call>
{{"name": "Werkzeugname", "parameters": {{"Parametername": "Parametwert"}}}}
<tool_call>IC

【Antwortstil】
- Prägnant und direkt, ohne umfangreiche Erklärungen.
- Verwende > für zentrale Inhalte.
- Priorisiere Schlussfolgerungen vor Erklärungen."""

CHAT_OBSERVATION_SUFFIX = "\n\nBitte antworten Sie kurz auf die Frage."


# ═══════════════════════════════════════════════════════════════
# ReportAgent-Hauptklasse
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - Simulations-Berichtgenerierungs-Agent

    Verwendet den ReACT-Modus (Reasoning + Acting):
    1. Planungsphase: Simulationsanforderungen analysieren, Berichts-Gliederung planen
    2. Generierungsphase: Kapitelweise Inhalt generieren, pro Kapitel mehrfach Tools aufrufen
    3. Reflexionsphase: Vollständigkeit und Korrektheit des Inhalts prüfen
    """
    
    # Maximale Werkzeugaufrufe (pro Kapitel)
    MAX_TOOL_CALLS_PER_SECTION = 5
    
    # Maximale Reflexionsrunden
    MAX_REFLECTION_ROUNDS = 3
    
    # Maximale Werkzeugaufrufe im Dialog
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self, 
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None
    ):
        """
        Report Agent initialisieren
        
        Args:
            graph_id: Graph-ID
            simulation_id: Simulations-ID
            simulation_requirement: Beschreibung der Simulationsanforderung
            llm_client: LLM-Client (optional)
            zep_tools: Zep-Tool-Service (optional)
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        
        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        
        # Werkzeugdefinitionen
        self.tools = self._define_tools()
        
        # Logger (initialisiert in generate_report)
        self.report_logger: Optional[ReportLogger] = None
        # Konsolenlogger (initialisiert in generate_report)
        self.console_logger: Optional[ReportConsoleLogger] = None
        
        logger.info(t('report.agentInitDone', graphId=graph_id, simulationId=simulation_id))
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Definieren der verfügbaren Werkzeuge"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "Die Frage oder das Thema, zu dem Sie tiefer in die Analyse gehen möchten",
                    "report_context": "Der Kontext des aktuellen Berichtskapitels (optional, hilft bei der Erstellung präziserer Teilfragen)"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "Suche nach Abfragen, die für relevante Sortierung verwendet werden",
                    "include_expired": "Ob veraltete/geschichtliche Inhalte enthalten sind (Standardwert True)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Suchabfrage als String",
                    "limit": "Anzahl der zurückgegebenen Ergebnisse (optional, Standardwert 10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Thema oder Beschreibung des Interviews (z.B. 'Meinungen von Schülern zum Formaldehyd-Problem in den Wohnheimen')",
                    "max_agents": "Maximale Anzahl der Agenten für Interviews (optional, Standardwert 5, Maximalwert 10)"
                }
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        Tool-Aufruf ausführen
        
        Args:
            tool_name: Tool-Name
            parameters: Tool-Parameter
            report_context: Berichtskontext (für InsightForge)
            
        Returns:
            Tool-Ausführungsergebnis (Textformat)
        """
        logger.info(t('report.executingTool', toolName=tool_name, params=parameters))
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                # Breitensuche - Erhalte den Gesamtausblick
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                # Einfache Suche - Schnelle Abfrage
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                # Tiefe Interview - Aufruf des echten OASIS-Interview-APIs zur Erhaltung der Antwort des simulierten Agents (dual-platform)
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()
            
            # ========== Rückwärtskompatibilität für alte Werkzeuge (interne Umleitung zu neuen Werkzeugen) ==========
            
            elif tool_name == "search_graph":
                # Umleitung zu quick_search
                logger.info(t('report.redirectToQuickSearch'))
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                # Umleitung zu insight_forge, da es stärker ist
                logger.info(t('report.redirectToInsightForge'))
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f"Unbekanntes Tool: {tool_name}. Bitte verwende eines der folgenden Tools: insight_forge, panorama_search, quick_search"
                
        except Exception as e:
            logger.error(t('report.toolExecFailed', toolName=tool_name, error=str(e)))
            return f"Tool-Ausführung fehlgeschlagen: {str(e)}"
    
    # Legale Werkzeugnamenssammlung zur Überprüfung bei der Auswertung des nackten JSON-Fallbacks
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Tool-Aufrufe aus LLM-Antwort parsen

        Unterstützte Formate (nach Priorität):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Rohes JSON (Antwort insgesamt oder einzelne Zeile ist ein Tool-Aufruf-JSON)
        """
        tool_calls = []

        # Format 1: XML-Stil (Standardformat)
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format 2: Fallback - LLM gibt unverpacktes JSON direkt aus
        # Versuche nur bei Format 1, um Missmatches im Text zu vermeiden
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # Antwort kann Gedankenblase + nacktes JSON enthalten, versuche das letzte JSON-Objekt zu extrahieren
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Überprüfen der Gültigkeit des analysierten JSON als Werkzeugaufruf"""
        # Unterstützt {"name": ..., "parameters": ...} und {"tool": ..., "params": ...} zwei Schlüsselnamen
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # Schlüsselnamen auf name / parameters einheitlich setzen
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """Erstellen eines Textes zur Beschreibung des Tools"""
        desc_parts = ["Verfügbare Werkzeuge:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parameter: {params_desc}")
        return "\n".join(desc_parts)
    
    def plan_outline(
        self, 
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Berichts-Gliederung planen
        
        Verwendet LLM zur Analyse der Simulationsanforderungen und plant die Inhaltsverzeichnisstruktur
        
        Args:
            progress_callback: Fortschritts-Callback-Funktion
            
        Returns:
            ReportOutline: Berichts-Gliederung
        """
        logger.info(t('report.startPlanningOutline'))
        
        if progress_callback:
            progress_callback("planning", 0, t('progress.analyzingRequirements'))
        
        # Erste Schritt: Simulationskontext abrufen
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, t('progress.generatingOutline'))
        
        system_prompt = f"{PLAN_SYSTEM_PROMPT}\n\n{get_language_instruction()}"
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, t('progress.parsingOutline'))
            
            # Übersicht analysieren
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "Simulierte Analyse des Berichts"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, t('progress.outlinePlanComplete'))
            
            logger.info(t('report.outlinePlanDone', count=len(sections)))
            return outline
            
        except Exception as e:
            logger.error(t('report.outlinePlanFailed', error=str(e)))
            # Standardübersicht zurückgeben (3 Kapitel, als Fallback)
            return ReportOutline(
                title="Zukunftsvorhersage-Bericht",
                summary="Analyse zukünftiger Trends und Risiken basierend auf simulierten Vorhersagen",
                sections=[
                    ReportSection(title="Zusammenfassung der Szenarien und Kernergebnisse"),
                    ReportSection(title="Analyse zukünftiger Verhaltensweisen von Gruppen"),
                    ReportSection(title="Zukunftsperspektiven und Risikohinweise")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        Einzelnes Kapitel im ReACT-Modus generieren
        
        ReACT-Zyklus:
        1. Thought (Denken) - Analysieren welche Informationen benötigt werden
        2. Action (Handeln) - Tools aufrufen um Informationen zu erhalten
        3. Observation (Beobachten) - Tool-Ergebnisse analysieren
        4. Wiederholen bis genug Informationen vorhanden oder Maximum erreicht
        5. Final Answer (Endantwort) - Kapitelinhalt generieren
        
        Args:
            section: Zu generierendes Kapitel
            outline: Vollständige Gliederung
            previous_sections: Inhalt vorheriger Kapitel (für Kohärenz)
            progress_callback: Fortschritts-Callback
            section_index: Kapitelindex (für Protokollierung)
            
        Returns:
            Kapitelinhalt (Markdown-Format)
        """
        logger.info(t('report.reactGenerateSection', title=section.title))
        
        # Kapitelbeginn-Protokoll aufzeichnen
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        # Benutzerprompt bauen - jedes abgeschlossene Kapitel bis zu maximal 4000 Zeichen übermitteln
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # Jedes Kapitel maximal 4000 Zeichen
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(Dies ist der erste Abschnitt)"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACT-Schleife
        tool_calls_count = 0
        max_iterations = 5  # Maximale Anzahl der Iterationen
        min_tool_calls = 3  # Mindestanzahl der Werkzeugaufrufe
        conflict_retries = 0  # Anzahl der aufeinanderfolgenden Konflikte, bei denen Werkzeugaufruf und Final Answer gleichzeitig auftreten
        used_tools = set()  # Aufgezeichnete Werkzeugnamen
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # Berichtskontext, für die Erstellung von Unterfragen in InsightForge
        report_context = f"Kapiteltitel: {section.title}\nSimulationsanforderung: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    t('progress.deepSearchAndWrite', current=tool_calls_count, max=self.MAX_TOOL_CALLS_PER_SECTION)
                )
            
            # Rufe LLM auf
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # Überprüfen, ob LLM-Antwort None ist (API-Fehler oder leere Inhalte)
            if response is None:
                logger.warning(t('report.sectionIterNone', title=section.title, iteration=iteration + 1))
                # Wenn noch Iterationen übrig sind, Nachricht hinzufügen und erneut versuchen
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(Keine Antwort vorhanden)"})
                    messages.append({"role": "user", "content": "Bitte fahren Sie mit dem Erstellen von Inhalten fort."})
                    continue
                # Letzte Iteration auch None zurückgibt, Schleife verlassen und forcierte Beendigung einleiten
                break

            logger.debug(f"LLM-Antwort: {response[:200]}...")

            # Einmalig analysieren, Ergebnis wiederverwenden
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── Konfliktbehandlung: LLM gibt Werkzeugaufruf und Final Answer gleichzeitig aus ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    t('report.sectionConflict', title=section.title, iteration=iteration+1, conflictCount=conflict_retries)
                )

                if conflict_retries <= 2:
                    # Erste beiden Male: Antwort ignorieren, LLM erneut antworten lassen
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Formatfehler] Du hast in einer Antwort gleichzeitig einen Werkzeugaufruf und eine finale Antwort eingeschlossen, was nicht erlaubt ist.\n"
                            "Jede Antwort kann nur eines der folgenden beiden tun:\n"
                            "- Aufruf eines Werkzeugs (Ausgabe eines IFC-Blocks, keine finale Antwort schreiben)\n"
                            "- Ausgabe des finalen Inhalts (mit 'Final Answer:' als Präfix, kein IFC enthalten)\n"
                            "Bitte antworten Sie erneut und tun Sie nur eines der beiden."
                        ),
                    })
                    continue
                else:
                    # Dritte Mal: Niedrigstes Verfahren anwenden, bis zum ersten Werkzeugaufruf abschneiden und forciert ausführen
                    logger.warning(
                        t('report.sectionConflictDowngrade', title=section.title, conflictCount=conflict_retries)
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # LLM-Antwortprotokoll aufzeichnen
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # ── Fall 1: LLM gibt Final Answer aus ──
            if has_final_answer:
                # Werkzeugaufrufe sind zu wenige, ablehnen und Werkzeuganruf forciert
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"(Diese Tools wurden noch nicht verwendet, Empfehlung: {', '.join(unused_tools)}）" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # Normaler Abschluss
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(t('report.sectionGenDone', title=section.title, count=tool_calls_count))

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # ── Fall 2: LLM versucht Werkzeug zu aufrufen ──
            if has_tool_calls:
                # Werkzeugaufrufe sind erschöpft → explizit informieren und Final Answer anfordern
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # Nur den ersten Werkzeugaufruf ausführen
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(t('report.multiToolOnlyFirst', total=len(tool_calls), toolName=call['name']))

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # Unbenutzte Werkzeuge aufzählen
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list="、".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # ── Fall 3: Kein Werkzeugaufruf und kein Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Werkzeugaufrufe sind zu wenige, unbenutzte Werkzeuge empfehlen
                unused_tools = all_tools - used_tools
                unused_hint = f"(Diese Tools wurden noch nicht verwendet, Empfehlung: {', '.join(unused_tools)}）" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Werkzeugaufrufe sind ausreichend, LLM gibt Inhalte ohne "Final Answer:"-Präfix aus
            # Den Inhalt direkt als Endantwort verwenden und nicht leerlaufen
            logger.info(t('report.sectionNoPrefix', title=section.title, count=tool_calls_count))
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # Maximale Anzahl der Iterationen erreicht, forcierte Inhaltsgenerierung
        logger.warning(t('report.sectionMaxIter', title=section.title))
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # Überprüfen, ob LLM-Antwort bei forciertem Abschluss None ist
        if response is None:
            logger.error(t('report.sectionForceFailed', title=section.title))
            final_answer = t('report.sectionGenFailedContent')
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # Kapitelinhalt-Generierung-Vollendung-Protokoll aufzeichnen
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Vollständigen Bericht generieren (kapitelweise Echtzeit-Ausgabe)
        
        Jedes fertige Kapitel wird sofort gespeichert, ohne auf den gesamten Bericht zu warten.
        Dateistruktur:
        reports/{report_id}/
            meta.json       - Bericht-Metainformationen
            outline.json    - Berichts-Gliederung
            progress.json   - Generierungsfortschritt
            section_01.md   - Kapitel 1
            section_02.md   - Kapitel 2
            ...
            full_report.md  - Vollständiger Bericht
        
        Args:
            progress_callback: Fortschritts-Callback-Funktion (stage, progress, message)
            report_id: Bericht-ID (optional, wird sonst automatisch generiert)
            
        Returns:
            Report: Vollständiger Bericht
        """
        import uuid
        
        # Wenn kein report_id übergeben wird, automatisch generieren
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        # Abgeschlossene Kapitelüberschriffliste (für Fortschrittsverfolgung)
        completed_section_titles = []
        
        try:
            # Initialisierung: Erstellen des Berichtsordners und Speichern der Anfangszustände
            ReportManager._ensure_report_folder(report_id)
            
            # Initialisiere Log-Recorder (strukturierte Logs agent_log.jsonl)
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )
            
            # Initialisiere Konsole-Log-Recorder (console_log.txt)
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, t('progress.initReport'),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            # Phase 1: Planung der Struktur
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, t('progress.startPlanningOutline'),
                completed_sections=[]
            )
            
            # Protokolliere Start des Plans
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, t('progress.startPlanningOutline'))
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            # Protokolliere Fertigstellung des Plans
            self.report_logger.log_planning_complete(outline.to_dict())
            
            # Speichere Struktur in Datei
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, t('progress.outlineDone', count=len(outline.sections)),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(t('report.outlineSavedToFile', reportId=report_id))
            
            # Phase 2: Generierung Kapitelweise (Kapitelweise speichern)
            report.status = ReportStatus.GENERATING
            
            total_sections = len(outline.sections)
            generated_sections = []  # Speichere Inhalte für Kontext
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                # Aktualisiere Fortschritt
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    t('progress.generatingSection', title=section.title, current=section_num, total=total_sections),
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        t('progress.generatingSection', title=section.title, current=section_num, total=total_sections)
                    )
                
                # Generiere Hauptkapitelinhalt
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # Speichere Kapitel
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # Protokolliere Fertigstellung des Kapitels
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(t('report.sectionSaved', reportId=report_id, sectionNum=f"{section_num:02d}"))
                
                # Aktualisiere Fortschritt
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    t('progress.sectionDone', title=section.title),
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            # Phase 3: Zusammenstellen vollständigen Berichts
            if progress_callback:
                progress_callback("generating", 95, t('progress.assemblingReport'))
            
            ReportManager.update_progress(
                report_id, "generating", 95, t('progress.assemblingReport'),
                completed_sections=completed_section_titles
            )
            
            # Verwende ReportManager zum Zusammenstellen des Berichts
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            # Berechne Gesamtlaufzeit
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # Protokolliere Fertigstellung des Berichts
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            # Speichere endgültigen Bericht
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, t('progress.reportComplete'),
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, t('progress.reportComplete'))
            
            logger.info(t('report.reportGenDone', reportId=report_id))
            
            # Schließe Konsole-Log-Recorder
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
            
        except Exception as e:
            logger.error(t('report.reportGenFailed', error=str(e)))
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # Protokolliere Fehlerlog
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # Speichere fehlgeschlagenen Status
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, t('progress.reportFailed', error=str(e)),
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # Ignoriere Fehlspeicherung Fehler
            
            # Schließe Konsole-Log-Recorder
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Mit dem Report Agent kommunizieren
        
        Im Gespräch kann der Agent eigenständig Retrieval-Tools aufrufen um Fragen zu beantworten
        
        Args:
            message: Benutzernachricht
            chat_history: Gesprächsverlauf
            
        Returns:
            {
                "response": "Agent-Antwort",
                "tool_calls": [Liste aufgerufener Tools],
                "sources": [Informationsquellen]
            }
        """
        logger.info(t('report.agentChat', message=message[:50]))
        
        chat_history = chat_history or []
        
        # Holte generierte Berichtsinhalte
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # Beschränke Berichtslänge, um Kontext zu vermeiden
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [Berichtsinhalte abgeschnitten] ..."
        except Exception as e:
            logger.warning(t('report.fetchReportFailed', error=e))
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(Kein Bericht vorhanden)",
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        # Erstelle Nachricht
        messages = [{"role": "system", "content": system_prompt}]
        
        # Füge historische Dialoge hinzu
        for h in chat_history[-10:]:  # Beschränke Historie
            messages.append(h)
        
        # Füge Benutzer-Nachricht hinzu
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # ReACT-Schleife (vereinfacht)
        tool_calls_made = []
        max_iterations = 2  # Verringere Anzahl Iterationen
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            # Analysiere Werkzeugaufruf
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # Kein Werkzeugaufruf, gib direkten Antwort zurück
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # Führe Werkzeugaufruf aus (beschränkt)
            tool_results = []
            for call in tool_calls[:1]:  # Maximal ein Werkzeugaufruf pro Runde
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # Beschränke Ergebnislänge
                })
                tool_calls_made.append(call)
            
            # Füge Ergebnis zur Nachricht hinzu
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']}Ergebnisse]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # Erreicht maximale Iteration, gib endgültige Antwort zurück
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        # Reinige Antwort
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    Bericht-Manager
    
    Zuständig für persistente Speicherung und Abruf von Berichten
    
    Dateistruktur (kapitelweise Ausgabe):
    reports/
      {report_id}/
        meta.json          - Bericht-Metainformationen und Status
        outline.json       - Berichts-Gliederung
        progress.json      - Generierungsfortschritt
        section_01.md      - Kapitel 1
        section_02.md      - Kapitel 2
        ...
        full_report.md     - Vollständiger Bericht
    """
    
    # Berichts-Speicher-Verzeichnis
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """Sicherstellen, dass der Berichtsrootordner existiert"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """Abrufen des Pfades zum Berichtsverzeichnis"""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Sicherstellen, dass das Berichtsverzeichnis existiert und den Pfad zurückgeben"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Abrufen des Pfades zur Metadaten-Datei des Berichts"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Abrufen des Pfades zur vollständigen Berichtsdatei in Markdown"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Gliederungs-Dateipfad abrufen"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Fortschritts-Dateipfad abrufen"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Kapitel-Markdown-Dateipfad abrufen"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Agent-Protokoll-Dateipfad abrufen"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Konsolenprotokoll-Dateipfad abrufen"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Holt den Inhalt der Konsolenprotokolle.
        
        Dies ist die Ausgabe des Kontrollfelds während des Berichtserstellungsprozesses (INFO, WARNING usw.),
        und unterscheidet sich von der strukturierten Protokollierung in agent_log.jsonl.
        
        Args:
            report_id: ID des Berichts
            from_line: Ab welcher Zeile gelesen werden soll (für inkrementelle Abfragen, 0 bedeutet Anfang)
            
        Returns:
            {
                "logs": [Liste der Protokolleinträge],
                "total_lines": Gesamtzahl der Zeilen,
                "from_line": Startzeilennummer,
                "has_more": Gibt an, ob es noch mehr Protokolle gibt
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # Behalte Original-Log-Zeilen, entferne Endzeilenumbruch
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Gekennzeichnet als Ende
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Holt den kompletten Konsolenprotokoll (einmalige Abfrage).
        
        Args:
            report_id: ID des Berichts
            
        Returns:
            Liste der Protokolleinträge.
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Holt den Inhalt der Agent-Protokolle.
        
        Args:
            report_id: ID des Berichts
            from_line: Ab welcher Zeile gelesen werden soll (für inkrementelle Abfragen, 0 bedeutet Anfang)
            
        Returns:
            {
                "logs": [Liste der Protokolleinträge],
                "total_lines": Gesamtzahl der Zeilen,
                "from_line": Startzeilennummer,
                "has_more": Gibt an, ob es noch mehr Protokolle gibt
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Überspringe fehlschlagende Zeilen
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Gekennzeichnet als Ende
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Holt den kompletten Agent-Protokoll (einmalige Abfrage).
        
        Args:
            report_id: ID des Berichts
            
        Returns:
            Liste der Protokolleinträge.
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Speichert den Berichtsentwurf.
        
        Wird direkt nach dem Abschluss des Planungsstages aufgerufen.
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(t('report.outlineSaved', reportId=report_id))
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        Speichert ein einzelnes Kapitel.

        Wird direkt nach der Erstellung jedes Kapitels aufgerufen, um die Kapitelweise Ausgabe zu gewährleisten.

        Args:
            report_id: ID des Berichts
            section_index: Index des Kapitels (beginnt bei 1)
            section: Kapitelobjekt

        Returns:
            Pfad des gespeicherten Dateis.
        """
        cls._ensure_report_folder(report_id)

        # Bau Kapitel-Markdown-Inhalt - Bereinige mögliche doppelte Überschriften
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # Speichere Datei
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(t('report.sectionFileSaved', reportId=report_id, fileSuffix=file_suffix))
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Bereinigt den Inhalt eines Kapitels.
        
        1. Entfernt Markdown-Kopfzeilen, die mit dem Kapiteltitel übereinstimmen
        2. Wandelt alle ### und niedrigeren Titel in Fettschrift um
        
        Args:
            content: Ursprünglicher Inhalt
            section_title: Kapiteltitle
            
        Returns:
            Bereinigter Inhalt.
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Überprüfe, ob es sich um eine Markdown-Überschrift handelt
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # Überprüfe, ob es sich um eine doppelte Überschrift handelt (überspringe Doppeltere in den ersten 5 Zeilen)
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # Konvertiere alle Ebenen von Überschriften (#, ##, ###, #### usw.) in Fettdruck
                # Da Kapitelüberschriften vom System hinzugefügt werden, sollte der Inhalt keine Überschriften enthalten
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # Füge leere Zeilen hinzu
                continue
            
            # Überspringe, wenn die vorherige Zeile eine übersprungene Überschrift ist und die aktuelle Zeile leer ist
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # Entferne leere Zeilen am Anfang
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # Entferne Trennlinien am Anfang
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # Entferne leere Zeilen nach der Trennlinie
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        Aktualisiert den Fortschritt der Berichtserstellung.
        
        Die Frontend kann die aktuelle Fortschrittsinformation durch das Lesen von progress.json abrufen.
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Berichterstellungsfortschritt abrufen"""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Holt eine Liste der bereits erstellten Kapitel.
        
        Gibt alle gespeicherten Kapiteldateiinformationen zurück.
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Analysiere Kapitelindex aus Dateinamen
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        Erstellt den vollständigen Bericht.
        
        Erstellt den vollständigen Bericht aus den gespeicherten Kapiteldateien und bereinigt die Titel.
        """
        folder = cls._get_report_folder(report_id)
        
        # Bau Berichtsheader
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        # Lese alle Kapiteldateien in der richtigen Reihenfolge
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # Nachbearbeitung: Bereinige Probleme mit Überschriften im gesamten Bericht
        md_content = cls._post_process_report(md_content, outline)
        
        # Speichere vollständigen Bericht
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(t('report.fullReportAssembled', reportId=report_id))
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        Nachbearbeitung des Berichtsinhalts.
        
        1. Entfernt doppelte Titel
        2. Behält Haupttitel (#) und Kapiteltitel (##) bei, entfernt andere Titel (###, #### usw.)
        3. Bereinigt überflüssige Leerzeilen und Trennzeichen.
        
        Args:
            content: Ursprünglicher Berichtsinhalt
            outline: Berichtsentwurf
            
        Returns:
            Bearbeiteter Inhalt.
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # Sammle alle Kapitelüberschriften im Inhaltsverzeichnis
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Überprüfe, ob es sich um eine Überschrift handelt
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Überprüfe, ob es sich um eine doppelte Überschrift handelt (gleiche Inhalte in den ersten 5 Zeilen)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # Überspringe doppelte Überschriften und leere Zeilen danach
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # Bearbeite Überschriftenebenen:
                # - # (level=1) behalte nur den Haupttitel des Berichts
                # - ## (level=2) behalte Kapitelüberschriften
                # - ### und niedriger (level>=3) konvertiere in Fettdrucktext
                
                if level == 1:
                    if title == outline.title:
                        # Behalte den Haupttitel des Berichts
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # Kapitelüberschriften, die # verwenden, korrigiere auf ##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # Andere Haupttitel in Fettdrucktext konvertieren
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # Behalte Kapitelüberschriften
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # Andere Kapitelüberschriften in Fettdrucktext konvertieren
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### und niedriger Überschriften in Fettdrucktext konvertieren
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # Überspringe Trennlinien direkt nach Überschriften
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # Behalte nur eine leere Zeile nach Überschriften
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # Bereinige mehrere aufeinanderfolgende leere Zeilen (behalte maximal 2)
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """Bericht-Metadaten und vollständigen Bericht speichern"""
        cls._ensure_report_folder(report.report_id)
        
        # Speichere Metainformationen JSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Speichere Inhaltsverzeichnis
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        # Speichere vollständigen Markdown-Bericht
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(t('report.reportSaved', reportId=report.report_id))
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Bericht abrufen"""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # Neue Formatierung: Ordner
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Rekonstruiere Report-Objekt
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # Versuche, den Inhalt aus full_report.md zu lesen, wenn markdown_content leer ist
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """Bericht nach Simulations-ID abrufen"""
        cls._ensure_reports_dir()
        
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # Neue Formatierung: Ordner
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # Kompatibilität mit altem Format: JSON-Datei
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report
        
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """Berichte auflisten"""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # Neue Formatierung: Ordner
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # Kompatibilität mit altem Format: JSON-Datei
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        # nach Erstellungszeit umgekehrt sortieren
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Bericht löschen (gesamter Ordner)"""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        # neues Format: gesamten Ordner löschen
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(t('report.reportFolderDeleted', reportId=report_id))
            return True
        
        # Kompatibilität mit altem Format: einzelnen Datei löschen
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted
