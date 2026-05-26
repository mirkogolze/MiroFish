"""
Zep retrieval tool service
Encapsulates graph search, node reading, and edge querying tools for the Report Agent to use.

Core retrieval tools (optimized):
1. InsightForge (deep insight retrieval) - The most powerful hybrid retrieval that automatically generates sub-questions and retrieves in multiple dimensions.
2. PanoramaSearch (breadth search) - Retrieves a complete overview including expired content.
3. QuickSearch (simple search) - Fast retrieval.
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_locale, t
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_tools')


@dataclass
class SearchResult:
    """Suchergebnisse"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """Konvertiere in Textformat, damit LLM es verstehen kann"""
        text_parts = [f"Suchanfrage: {self.query}", f"Gefunden: {self.total_count} relevante Informationen"]
        
        if self.facts:
            text_parts.append("\n### Verwandte Fakten:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Knoteninformation"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """Konvertiere in Textformat"""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "Unbekannter Typ")
        return f"Entitäten: {self.name} (Typ: {entity_type})\nZusammenfassung: {self.summary}"


@dataclass
class EdgeInfo:
    """Nebeninformation"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # Zeitinformation
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """Konvertiere in Textformat"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Beziehungen: {source} --[{self.name}]--> {target}\nFakten: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "Unbekannt"
            invalid_at = self.invalid_at or "Bisher"
            base_text += f"\nGültigkeit: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (abgelaufen: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """Ist abgelaufen"""
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        """Ist ungültig"""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    Deep insight retrieval result (InsightForge)
    Contains the results of multiple sub-questions and comprehensive analysis
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # Suchergebnisse für verschiedene Dimensionen
    semantic_facts: List[str] = field(default_factory=list)  # Semantische Suchergebnisse
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # Entitätsinsight
    relationship_chains: List[str] = field(default_factory=list)  # Verbindungen
    
    # Statistiken
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """In detaillierte Textformat umwandeln, damit LLM es verstehen kann"""
        text_parts = [
            f"## Zukunftsprognose-Tiefenanalyse",
            f"Problem analysieren: {self.query}",
            f"Vorhersageszenario: {self.simulation_requirement}",
            f"\n### Vorhersagedatenstatistik",
            f"- relevante Vorhersagefakten:{self.total_facts}Stück",
            f"- beteiligte Entitäten:{self.total_entities} Stk.",
            f"- Verbindungsreihenfolge:{self.total_relationships}Stück"
        ]
        
        # Unterfrage
        if self.sub_queries:
            text_parts.append(f"\n### Teilprobleme der Analyse")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # Semantische Suchergebnisse
        if self.semantic_facts:
            text_parts.append(f"\n### 【Kritische Fakten】(Bitte zitieren Sie diese Originaltexte im Bericht)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Entitätsinsight
        if self.entity_insights:
            text_parts.append(f"\n### 【Kernentitäten】")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'Unbekannt')}** ({entity.get('type', 'Entität')})")
                if entity.get('summary'):
                    text_parts.append(f"  Zusammenfassung:{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  Verwandte Fakten:{len(entity.get('related_facts', []))}Stück")
        
        # Verbindungen
        if self.relationship_chains:
            text_parts.append(f"\n### 【Verbindungsreihenfolge】")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    Breadth search result (Panorama)
    Includes all relevant information, including expired content.
    """
    query: str
    
    # Alle Knoten
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # Alle Kanten (inklusive abgelaufen)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # Aktuell gültige Fakten
    active_facts: List[str] = field(default_factory=list)
    # Abgelaufene/ungültige Fakten (Historie)
    historical_facts: List[str] = field(default_factory=list)
    
    # Statistik
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """In Textformat umwandeln (vollständige Version, ohne Abschnitte)"""
        text_parts = [
            f"## Breitensuchergebnisse (Zukunftsgesamtansicht)",
            f"Abfrage:{self.query}",
            f"\n### Statistische Informationen",
            f"- Gesamtzahl der Knoten:{self.total_nodes}",
            f"- Gesamtzahl der Kanten:{self.total_edges}",
            f"- aktuelle gültige Fakten:{self.active_count}Stück",
            f"- historische/abgelaufene Fakten:{self.historical_count}Stück"
        ]
        
        # Aktuell gültige Fakten (komplette Ausgabe, nicht abgeschnitten)
        if self.active_facts:
            text_parts.append(f"\n### 【aktuelle gültige Fakten】(Simulationsergebnisse im Originaltext)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Historische/abgelaufene Fakten (komplette Ausgabe, nicht abgeschnitten)
        if self.historical_facts:
            text_parts.append(f"\n### 【historische/abgelaufene Fakten】(Evolutionsprozessprotokolle)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Kritische Entitäten (komplette Ausgabe, nicht abgeschnitten)
        if self.all_nodes:
            text_parts.append(f"\n### 【beteiligte Entitäten】")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entität")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """Interviewergebnis eines einzelnen Agenten"""
    agent_name: str
    agent_role: str  # Rollenarten (z.B. Schüler, Lehrer, Medien usw.)
    agent_bio: str  # Kurzbiografie
    question: str  # Interviewfragen
    response: str  # Interviewantworten
    key_quotes: List[str] = field(default_factory=list)  # Kritische Zitate
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # Komplette Agent-Biografie anzeigen, nicht abgeschnitten
        text += f"_Kurzbeschreibung:{self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Kritische Zitate:**\n"
            for quote in self.key_quotes:
                # Verschiedene Anführungszeichen bereinigen
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # Anfangszeichen entfernen
                while clean_quote and clean_quote[0] in '，,；;：:、。！？\n\r\t ':
                    clean_quote = clean_quote[1:]
                # Inhalt filtern, der Nummern von Fragen enthält (Fragen 1-9)
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # Zu lange Inhalte abschneiden (an Perioden, nicht an festgelegten Stellen)
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    Interview results (Interview)
    Contains multiple simulated Agent interview responses
    """
    interview_topic: str  # Interviewthema
    interview_questions: List[str]  # Liste der Interviewfragen
    
    # Ausgewählter Agent für das Interview
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # Interviewantworten aller Agents
    interviews: List[AgentInterview] = field(default_factory=list)
    
    # Gründe für die Auswahl des Agenten
    selection_reasoning: str = ""
    # Zusammengefasste Interviewzusammenfassung
    summary: str = ""
    
    # Statistik
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """In detaillierte Textformat umwandeln, damit LLM es verstehen und zitieren kann"""
        text_parts = [
            "## Tiefeninterviewbericht",
            f"**Interviewthema:**{self.interview_topic}",
            f"**Anzahl der Interviewteile:**{self.interviewed_count} / {self.total_agents} Simulierte Agent",
            "\n### Gründe für die Auswahl des Interviewpartners",
            self.selection_reasoning or "(automatische Auswahl)",
            "\n---",
            "\n### Interviewprotokoll",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(kein Interviewprotokoll)\n\n---")

        text_parts.append("\n### Zusammenfassung des Interviews und Kernpunkte")
        text_parts.append(self.summary or "(keine Zusammenfassung)")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zep retrieval tool service
    
    【Core retrieval tools - optimized】
    1. insight_forge - Deep insight retrieval (most powerful, automatically generates sub-questions, multi-dimensional retrieval)
    2. panorama_search - Breadth search (retrieves a complete overview including expired content)
    3. quick_search - Simple search (fast retrieval)
    4. interview_agents - In-depth interviews (interviews simulated Agents to obtain multiple perspectives)

    【Basic tools】
    - search_graph - Graph semantic search
    - get_all_nodes - Retrieves all nodes in the graph
    - get_all_edges - Retrieves all edges in the graph (including time information)
    - get_node_detail - Retrieves detailed node information
    - get_node_edges - Retrieves edges related to a node
    - get_entities_by_type - Retrieves entities by type
    - get_entity_summary - Retrieves an entity's relationship summary
    """
    
    # Wiederholungs-Konfiguration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY nicht konfiguriert")
        
        self.client = Zep(api_key=self.api_key)
        # LLM-Client für InsightForge zur Erstellung von Unterfragen
        self._llm_client = llm_client
        logger.info(t("console.zepToolsInitialized"))
    
    @property
    def llm(self) -> LLMClient:
        """Verschobene Initialisierung des LLM-Client"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """API-Aufruf mit Wiederholungsmechanismus"""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        t("console.zepRetryAttempt", operation=operation_name, attempt=attempt + 1, error=str(e)[:100], delay=f"{delay:.1f}")
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(t("console.zepAllRetriesFailed", operation=operation_name, retries=max_retries, error=str(e)))
        
        raise last_exception
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graph semantic search

        Uses hybrid search (semantic + BM25) to search for relevant information in the graph.
        If Zep Cloud's search API is unavailable, it degrades to local keyword matching.

        Args:
            graph_id: Graph ID (Standalone Graph)
            query: Search query
            limit: Number of results returned
            scope: Search scope, "edges" or "nodes"

        Returns:
            SearchResult: Search result
        """
        logger.info(t("console.graphSearch", graphId=graph_id, query=query[:50]))
        
        # Versuche, Zep Cloud Search API zu verwenden
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=t("console.graphSearchOp", graphId=graph_id)
            )
            
            facts = []
            edges = []
            nodes = []
            
            # Analyse der Kanten-Suchergebnisse
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })
            
            # Analyse der Knoten-Suchergebnisse
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # Knotensummary gilt auch als Fakt
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.searchComplete", count=len(facts)))
            
            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )
            
        except Exception as e:
            logger.warning(t("console.zepSearchApiFallback", error=str(e)))
            # Degradation: Verwende lokale Keyword-Matching-Suche
            return self._local_search(graph_id, query, limit, scope)
    
    def _local_search(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Local keyword matching search (as a fallback for Zep Search API)

        Retrieves all edges/nodes and then performs local keyword matching.

        Args:
            graph_id: Graph ID
            query: Search query
            limit: Number of results returned
            scope: Search scope

        Returns:
            SearchResult: Search result
        """
        logger.info(t("console.usingLocalSearch", query=query[:30]))
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # Extrahiere Suchbegriffe (simple Tokenisierung)
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]
        
        def match_score(text: str) -> int:
            """Berechnung des Übereinstimmungsscores zwischen Text und Abfrage"""
            if not text:
                return 0
            text_lower = text.lower()
            # Genaue Übereinstimmung der Suche
            if query_lower in text_lower:
                return 100
            # Keyword-Matching
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score
        
        try:
            if scope in ["edges", "both"]:
                # Erhalte alle Kanten und passe an
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                
                # Sortiere nach Punktzahl
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })
            
            if scope in ["nodes", "both"]:
                # Alle Knoten abrufen und matchen
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.localSearchComplete", count=len(facts)))
            
        except Exception as e:
            logger.error(t("console.localSearchFailed", error=str(e)))
        
        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        Erhalte alle Knoten des Graphs (in Blöcken)

        Args:
            graph_id: Grafik-ID

        Returns:
            Eine Liste mit den Knoten
        """
        logger.info(t("console.fetchingAllNodes", graphId=graph_id))

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', None) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(t("console.fetchedNodes", count=len(result)))
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        Retrieves all edges in the graph (paged retrieval, including time information)

        Args:
            graph_id: Graph ID
            include_temporal: Whether to include time information (default True)

        Returns:
            List of edges (including created_at, valid_at, invalid_at, expired_at)
        """
        logger.info(t("console.fetchingAllEdges", graphId=graph_id))

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # Zeitinformation hinzufügen
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', None)
                edge_info.valid_at = getattr(edge, 'valid_at', None)
                edge_info.invalid_at = getattr(edge, 'invalid_at', None)
                edge_info.expired_at = getattr(edge, 'expired_at', None)

            result.append(edge_info)

        logger.info(t("console.fetchedEdges", count=len(result)))
        return result
    
    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        Retrieves detailed information for a single node

        Args:
            node_uuid: Node UUID

        Returns:
            Node information or None
        """
        logger.info(t("console.fetchingNodeDetail", uuid=node_uuid[:8]))
        
        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=t("console.fetchNodeDetailOp", uuid=node_uuid[:8])
            )
            
            if not node:
                return None
            
            return NodeInfo(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except Exception as e:
            logger.error(t("console.fetchNodeDetailFailed", error=str(e)))
            return None
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        Retrieves all edges related to a specified node

        By retrieving all edges in the graph and then filtering out those related to the specified node.

        Args:
            graph_id: Graph ID
            node_uuid: Node UUID

        Returns:
            List of edges
        """
        logger.info(t("console.fetchingNodeEdges", uuid=node_uuid[:8]))
        
        try:
            # Alle Kanten des Graphen abrufen und filtern
            all_edges = self.get_all_edges(graph_id)
            
            result = []
            for edge in all_edges:
                # Überprüfen, ob die Kante mit dem angegebenen Knoten verbunden ist (als Quelle oder Ziel)
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            
            logger.info(t("console.foundNodeEdges", count=len(result)))
            return result
            
        except Exception as e:
            logger.warning(t("console.fetchNodeEdgesFailed", error=str(e)))
            return []
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str
    ) -> List[NodeInfo]:
        """
        Retrieves entities by type

        Args:
            graph_id: Graph ID
            entity_type: Entity type (e.g. Student, PublicFigure)

        Returns:
            List of entities matching the specified type
        """
        logger.info(t("console.fetchingEntitiesByType", type=entity_type))
        
        all_nodes = self.get_all_nodes(graph_id)
        
        filtered = []
        for node in all_nodes:
            # Überprüfen, ob die Labels den angegebenen Typen entsprechen
            if entity_type in node.labels:
                filtered.append(node)
        
        logger.info(t("console.foundEntitiesByType", count=len(filtered), type=entity_type))
        return filtered
    
    def get_entity_summary(
        self, 
        graph_id: str, 
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Retrieves a summary of relationships for a specified entity

        Searches all information related to the entity and generates a summary.

        Args:
            graph_id: Graph ID
            entity_name: Entity name

        Returns:
            Summary information about the entity
        """
        logger.info(t("console.fetchingEntitySummary", name=entity_name))
        
        # Zuerst Informationen zu diesem Objekt suchen
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )
        
        # Versuchen, dieses Objekt in allen Knoten zu finden
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        
        related_edges = []
        if entity_node:
            # Übergeben von graph_id-Parameter
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
    
    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        Retrieves statistical information for a graph

        Args:
            graph_id: Graph ID

        Returns:
            Statistical information
        """
        logger.info(t("console.fetchingGraphStats", graphId=graph_id))
        
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        
        # Statistik über die Verteilung der Entitätstypen erstellen
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        
        # Statistik über die Verteilung der Beziehungsarten erstellen
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }
    
    def get_simulation_context(
        self, 
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        Retrieves context information related to simulations

        Comprehensive search for all information relevant to simulation requirements.

        Args:
            graph_id: Graph ID
            simulation_requirement: Description of the simulation requirement
            limit: Number limit per category of information

        Returns:
            Context information about the simulation
        """
        logger.info(t("console.fetchingSimContext", requirement=simulation_requirement[:50]))
        
        # Suche nach Informationen, die mit simulierten Anforderungen zusammenhängen
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )
        
        # Statistik des Graphen abrufen
        stats = self.get_graph_statistics(graph_id)
        
        # Alle Entitätsknoten abrufen
        all_nodes = self.get_all_nodes(graph_id)
        
        # Entitäten mit echtem Typ filtern (keine reinen Entity-Knoten)
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # Anzahl begrenzen
            "total_entities": len(entities)
        }
    
    # ========== Kernsuchwerkzeug (optimiert) ==========
    
    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        【InsightForge - Deep insight retrieval】

        The most powerful hybrid retrieval function that automatically breaks down problems and retrieves in multiple dimensions:
        1. Uses LLM to break the problem into several sub-questions.
        2. Performs semantic search on each sub-question.
        3. Extracts relevant entities and retrieves their detailed information.
        4. Tracks relationship chains.
        5. Integrates all results, generating deep insights.

        Args:
            graph_id: Graph ID
            query: User question
            simulation_requirement: Description of the simulation requirement
            report_context: Report context (optional, for more precise sub-question generation)
            max_sub_queries: Maximum number of sub-questions

        Returns:
            InsightForgeResult: Deep insight retrieval result
        """
        logger.info(t("console.insightForgeStart", query=query[:50]))
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        
        # Schritt 1: Verwenden von LLM, um Teilprobleme zu generieren
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(t("console.generatedSubQueries", count=len(sub_queries)))
        
        # Schritt 2: Semantische Suche für jedes Teilproblem durchführen
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # Suche auch für das Originalproblem durchführen
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Schritt 3: Extrahieren relevanter Entitäten-UUIDs aus den Kanten, nur diese Informationen abrufen (keine vollständige Knotenliste)
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # Alle relevanten Entitätendetails abrufen (ohne Anzahlbegrenzung, komplette Ausgabe)
        entity_insights = []
        node_map = {}  # Für die nachfolgende Verarbeitung der Beziehungen
        
        for uuid in list(entity_uuids):  # Verarbeiten aller Entitäten, ohne zu schneiden
            if not uuid:
                continue
            try:
                # Informationen für jeden relevanten Knoten einzeln abrufen
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entität")
                    
                    # Alle Fakten, die mit dieser Entität zusammenhängen, abrufen (ohne Anzahlbegrenzung)
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # Komplette Ausgabe ohne Schneiden
                    })
            except Exception as e:
                logger.debug(f"Knoten abrufen: {uuid} fehlgeschlagen: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Schritt 4: Erstellen aller Beziehungsreihen (ohne Anzahlbegrenzung)
        relationship_chains = []
        for edge_data in all_edges:  # Verarbeiten aller Kanten, ohne zu schneiden
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(t("console.insightForgeComplete", facts=result.total_facts, entities=result.total_entities, relationships=result.total_relationships))
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        Verwenden Sie LLM, um Teilprobleme zu generieren
        
        Teilen Sie komplexe Probleme in mehrere Teilprobleme auf, die unabhängig voneinander abgerufen werden können.
        """
        system_prompt = """Du bist ein Experte für die Analyse von Problemen. Deine Aufgabe ist es, komplexe Probleme in mehrere Teilprobleme zu zerlegen, die unabhängig voneinander im simulierten Weltmodell beobachtet werden können.

Anforderungen:
1. Jedes Teilproblem sollte spezifisch genug sein, um Agentverhalten oder -ereignisse im simulierten Weltmodell zu identifizieren.
2. Die Teilprobleme sollten verschiedene Aspekte des ursprünglichen Problems abdecken (wie: wer, was, warum, wie, wann, wo).
3. Die Teilprobleme sollten mit dem simulierten Szenario korreliert sein.
4. Rückgabe im JSON-Format: {"sub_queries": ["Teilproblem1", "Teilproblem2", ...]}"""

        user_prompt = f"""Simulationszweck:
{simulation_requirement}

{f"Berichtskontext:{report_context[:500]}" if report_context else ""}

Bitte zerlegen Sie die folgende Frage in{max_queries}Unterfragen:
{query}

Geben Sie die Liste der Unterfragen im JSON-Format zurück."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # Sicherstellen, dass es sich um eine Liste von Zeichenketten handelt
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(t("console.generateSubQueriesFailed", error=str(e)))
            # Degradieren: Rückgabe einer Variante basierend auf dem Originalproblem
            return [
                query,
                f"{query}Hauptakteure von",
                f"{query}Gründe und Auswirkungen von",
                f"{query}Entwicklungsgeschichte von"
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        【PanoramaSearch - Breitensuche】
        
        Erhalten Sie einen umfassenden Überblick, einschließlich aller relevanten Inhalte und historischen/abgelaufenen Informationen:
        1. Holen Sie alle relevanten Knoten ab
        2. Holen Sie alle Kanten (einschließlich abgelaufenen/unwirksamen) ab
        3. Organisieren Sie die aktuellen gültigen und historischen Informationen
        
        Diese Funktion eignet sich für Szenarien, in denen ein umfassender Überblick über Ereignisse oder deren Entwicklung erforderlich ist.
        
        Args:
            graph_id: Graph-ID
            query: Suchanfrage (zur Reihenfolge der Relevanz)
            include_expired: Soll abgelaufene Inhalte enthalten werden (Standardwert True)
            limit: Begrenzung der Anzahl der zurückgegebenen Ergebnisse
        
        Returns:
            PanoramaResult: Breitensuchergebnis
        """
        logger.info(t("console.panoramaSearchStart", query=query[:50]))
        
        result = PanoramaResult(query=query)
        
        # Hole alle Knoten
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        # Alle Kanten (mit Zeitinformation) abrufen
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # Fakten kategorisieren
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            # Entitätsnamen zu Fakten hinzufügen
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            
            # Überprüfen, ob veraltet/ungültig
            is_historical = edge.is_expired or edge.is_invalid
            
            if is_historical:
                # Historische/veraltete Fakten mit Zeitmarkierung hinzufügen
                valid_at = edge.valid_at or "Unbekannt"
                invalid_at = edge.invalid_at or edge.expired_at or "Unbekannt"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # Aktuell gültige Fakten
                active_facts.append(edge.fact)
        
        # Relevanz basierend auf der Abfrage sortieren
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]
        
        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score
        
        # Sortieren und Anzahl begrenzen
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(t("console.panoramaSearchComplete", active=result.active_count, historical=result.historical_count))
        return result
    
    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        【QuickSearch - Einfache Suche】
        
        Ein schnelles, leichtgewichtiges Suchwerkzeug:
        1. Direkter Aufruf der Zep-Semantischen Suche
        2. Rückgabe des am meisten relevanten Ergebnisses
        3. Für einfache und direkte Suchanforderungen geeignet
        
        Args:
            graph_id: Graph-ID
            query: Suchanfrage
            limit: Begrenzung der Anzahl der zurückgegebenen Ergebnisse
        
        Returns:
            SearchResult: Suchergebnis
        """
        logger.info(t("console.quickSearchStart", query=query[:50]))
        
        # Direkter Aufruf der existierenden search_graph-Methode
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(t("console.quickSearchComplete", count=result.total_count))
        return result
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        【InterviewAgents - Tiefeinterviews】
        
        Aufruf des echten OASIS-Interview-API, um Agenten in der Simulation zu interviewen:
        1. Automatische Lesung von Charakterdateien, um alle simulierten Agenten zu kennen
        2. Verwenden Sie LLM, um Interviewanforderungen zu analysieren und intelligente Auswahl des am meisten relevanten Agents vorzunehmen
        3. Verwenden Sie LLM, um Interviewfragen zu generieren
        4. Aufruf der /api/simulation/interview/batch-API für echte Interviews (Interviews auf beiden Plattformen gleichzeitig)
        5. Zusammenfassung aller Interviewergebnisse und Erstellung eines Interviewberichtes
        
        【Wichtig】Diese Funktion erfordert, dass die Simulationsumgebung aktiv ist (OASIS-Umgebung nicht geschlossen)
        
        【Verwendungsfallen】
        - Erfordernis, um Ereignisse aus verschiedenen Perspektiven zu verstehen
        - Erfordernis, um Meinungen und Ansichten von mehreren Parteien zu sammeln
        - Erfordernis, um echte Antworten der simulierten Agenten (keine LLM-Simulation) zu erhalten
        
        Args:
            simulation_id: Simulations-ID (zur Lokalisierung der Charakterdatei und Aufruf des Interview-API)
            interview_requirement: Beschreibung der Interviewanforderungen (unstrukturiert, z.B. "Verstehen Sie die Meinung der Schüler zu einem Ereignis")
            simulation_requirement: Hintergrund der Simulationsanforderungen (optional)
            max_agents: Maximale Anzahl der interviewten Agenten
            custom_questions: Benutzerdefinierte Interviewfragen (optional, wenn nicht bereitgestellt werden automatisch generiert)
        
        Returns:
            InterviewResult: Interviewergebnis
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(t("console.interviewAgentsStart", requirement=interview_requirement[:50]))
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Schritt 1: Lesen des Personendokuments
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(t("console.profilesNotFound", simId=simulation_id))
            result.summary = "Keine Datei für den Interviewagenten gefunden"
            return result
        
        result.total_agents = len(profiles)
        logger.info(t("console.loadedProfiles", count=len(profiles)))
        
        # Schritt 2: Verwenden von LLM, um Agenten für das Interview auszuwählen (Rückgabe einer Liste mit agent_id)
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(t("console.selectedAgentsForInterview", count=len(selected_agents), indices=selected_indices))
        
        # Schritt 3: Erstellen der Interviewfragen (falls nicht bereitgestellt)
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(t("console.generatedInterviewQuestions", count=len(result.interview_questions)))
        
        # Kombinieren der Fragen zu einem Interviewprompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # Hinzufügen eines Optimierungsprefixes, um die Antwortformat des Agents einzuschränken
        INTERVIEW_PROMPT_PREFIX = (
            "Du wirst ein Interview durchführen. Bitte beantworte die folgenden Fragen im Textformat."
            "Verwende deine Personendaten, Erinnerungen und Handlungen zur Antwort."
            "Anforderungen an die Antworten:"
            "1. Antwort in natürlicher Sprache, ohne Werkzeuge zu verwenden"
            "2. Keine JSON- oder Werkzeugaufrufformate"
            "3. Verwende keine Markdown-Titel (wie #, ##, ###)"
            "4. Beantworte die Fragen nacheinander und füge \"Frage X:\" vor jede Antwort ein"
            "5. Trenne die Antworten durch Leerzeilen"
            "6. Die Antworten müssen substanzreiche Inhalte haben, mindestens 2-3 Sätze pro Frage\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Schritt 4: Aufrufen der echten Interview-API (ohne Plattformangabe, standardmäßig beide Plattformen)
        try:
            # Erstellen einer Liste für das Batch-Interview (ohne Plattformangabe, Interview auf beiden Plattformen)
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # Verwenden des optimierten Prompts
                    # Ohne Plattformangabe, führt die API das Interview auf Twitter und Reddit aus
                })
            
            logger.info(t("console.callingBatchInterviewApi", count=len(interviews_request)))
            
            # Aufrufen der Batch-Interview-Methode von SimulationRunner (ohne Plattformangabe)
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # Ohne Plattformangabe, Interview auf beiden Plattformen
                timeout=180.0   # Beide Plattformen erfordern eine längere Timeout-Zeit
            )
            
            logger.info(t("console.interviewApiReturned", count=api_result.get('interviews_count', 0), success=api_result.get('success')))
            
            # Überprüfen, ob der API-Aufruf erfolgreich war
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "Unbekannter Fehler")
                logger.warning(t("console.interviewApiReturnedFailure", error=error_msg))
                result.summary = f"Interview-API-Aufruf fehlgeschlagen:{error_msg}. Bitte überprüfen Sie den OASIS-Simulationsstatus."
                return result
            
            # Schritt 5: Analysieren des API-Rückgabewerts und Erstellen eines AgentInterview-Objekts
            # Doppelplattformmodus Rückgabeformat: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "Unbekannt")
                agent_bio = agent.get("bio", "")
                
                # Abrufen der Interviewergebnisse für den Agenten auf beiden Plattformen
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # Aufräumen eventueller JSON-Umgebungen von Werkzeugaufrufen
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # Generieren des Doppelplattformmarkiers
                twitter_text = twitter_response if twitter_response else "(Die Plattform hat keine Antwort erhalten)"
                reddit_text = reddit_response if reddit_response else "(Die Plattform hat keine Antwort erhalten)"
                response_text = f"【Twitter-Plattform-Antwort】\n{twitter_text}\n\n【Reddit-Plattform-Antwort】\n{reddit_text}"

                # Extrahieren der zentralen Zitate (aus den Antworten auf beiden Plattformen)
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # Aufräumen des Antworttextes: Entfernen von Markierungen, Nummern und Markdown
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'Frage\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)

                # Strategie 1 (Haupt): Extrahieren vollständiger, substanzreicher Sätze
                sentences = re.split(r'[。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', 'Frage'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]

                # Strategie 2 (Ergänzung): Lange Texte innerhalb korrekter chinesischer Anführungszeichen ""
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # Erhöhen der Bio-Längengrenzen
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # Simulationsumgebung nicht ausgeführt
            logger.warning(t("console.interviewApiCallFailed", error=e))
            result.summary = f"Interview fehlgeschlagen:{str(e)}. Der OASIS-Umgebung könnte geschlossen sein, bitte stellen Sie sicher, dass die Umgebung läuft."
            return result
        except Exception as e:
            logger.error(t("console.interviewApiCallException", error=e))
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"Fehler während des Interviews:{str(e)}"
            return result
        
        # Schritt 6: Erstellen eines Interviewzusammenfassungs
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(t("console.interviewAgentsComplete", count=result.interviewed_count))
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Räumt Agent-Antworten von JSON-Werkzeugaufrufen frei, extrahiert den eigentlichen Inhalt"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Lädt die Agent-Charakterdatei für Simulationen"""
        import os
        import csv
        
        # Erstellen des Pfades für die Personendokumentation
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # Versuchen, das Reddit-JSON zu lesen
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(t("console.loadedRedditProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readRedditProfilesFailed", error=e))
        
        # Versuchen, den Twitter-CVS zu lesen
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # CSV-Format in einheitliches Format konvertieren
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "Unbekannt"
                        })
                logger.info(t("console.loadedTwitterProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readTwitterProfilesFailed", error=e))
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        Verwenden Sie LLM, um Agenten für die Interviews auszuwählen.
        
        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: Liste der vollständigen Informationen der ausgewählten Agenten
                - selected_indices: Liste der Indizes der ausgewählten Agenten (für API-Aufrufe)
                - reasoning: Auswahlgrund
        """
        
        # Erstellen der Agenten-Zusammenfassungsliste
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "Unbekannt"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """Sie sind ein Experte für Interviewplanung. Ihre Aufgabe ist es, basierend auf den Anforderungen der Interviews aus einer Liste von simulierten Agenten die besten Kandidaten zu wählen.

Auswahlkriterien:
1. Die Rolle/Profession des Agents ist mit dem Thema des Interviews verbunden
2. Der Agent könnte einzigartige oder wertvolle Perspektiven haben
3. Auswahl einer Vielfalt an Perspektiven (z.B.: Unterstützer, Gegner, Neutraler, Fachmann usw.)
4. Priorisierung von Rollen, die direkt mit dem Ereignis verbunden sind

Rückgabe in JSON-Format:
{
    "selected_indices": [Liste der Indizes der ausgewählten Agenten],
    "reasoning": "Gründe für die Auswahl"
}"""

        user_prompt = f"""Interviewanforderungen:
{interview_requirement}

Simulationszweck:
{simulation_requirement if simulation_requirement else "Nicht bereitgestellt"}

Verfügbare Agenten (insgesamt {len(agent_summaries)}):{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Bitte wählen Sie maximal {max_agents}geeignete Agenten aus und begründen Sie Ihre Wahl."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Basierend auf der Relevanz automatisch auswählen")
            
            # Abrufen der vollständigen Informationen des ausgewählten Agents
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(t("console.llmSelectAgentFailed", error=e))
            # Degradieren: Auswahl der ersten N
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "Verwende die Standardauswahlstrategie"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """Generiere Interviewfragen mit LLM"""
        
        agent_roles = [a.get("profession", "Unbekannt") for a in selected_agents]
        
        system_prompt = """Du bist ein professioneller Journalist/Interviewer. Erstelle basierend auf den Interviewanforderungen 3-5 tiefgründige Interviewfragen.

Anforderungen:
1. Offene Fragen, die detaillierte Antworten ermutigen.
2. Unterschiedliche Antworten je nach Rolle des Gesprächspartners.
3. Abdeckung von Fakten, Meinungen und Gefühlen.
4. Natürlicher Sprachgebrauch wie bei einem echten Interview.
5. Jede Frage sollte innerhalb von 50 Zeichen bleiben, prägnant und klar formuliert sein.
6. Stelle direkt Fragen ohne Hintergrundinformationen oder Präfixe.

Rückgabe im JSON-Format: {"questions": ["Frage1", "Frage2", ...]}"""

        user_prompt = f"""Interviewanforderungen:
{interview_requirement}

Simulationszweck:
{simulation_requirement if simulation_requirement else "Nicht bereitgestellt"}

Interviewobjekt-Rolle:{', '.join(agent_roles)}

Bitte generieren Sie 3-5 Interviewfragen."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f"Über{interview_requirement}, was ist Ihre Meinung?"])
            
        except Exception as e:
            logger.warning(t("console.generateInterviewQuestionsFailed", error=e))
            return [
                f"Über{interview_requirement}, was ist Ihre Meinung dazu?",
                "Wie hat diese Angelegenheit Sie oder die Gruppe, für die Sie sprechen, beeinflusst?",
                "Welche Maßnahmen schlagen Sie vor, um diese Angelegenheit zu lösen oder zu verbessern?"
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """Generiere Interviewzusammenfassung"""
        
        if not interviews:
            return "Kein Interview abgeschlossen"
        
        # Sammeln aller Interviewinhalte
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"【{interview.agent_name}（{interview.agent_role}）】\n{interview.response[:500]}")
        
        quote_instruction = "Verwende chinesische Anführungszeichen „“ für Zitate der Befragten" if get_locale() == 'zh' else 'Use quotation marks "" when quoting interviewees'
        system_prompt = f"""Du bist ein professioneller Nachrichtenredakteur. Erstelle basierend auf den Antworten mehrerer Befragter eine Interview-Zusammenfassung.

Anforderungen:
1. Hauptstandpunkte aller Parteien herausarbeiten
2. Konsens und Meinungsverschiedenheiten aufzeigen
3. Wertvolle Zitate hervorheben
4. Objektiv und neutral, keine Partei bevorzugen
5. Maximal 1000 Wörter

Format-Vorgaben (müssen befolgt werden):
- Reine Textabsätze, durch Leerzeilen getrennt
- Keine Markdown-Überschriften (#, ##, ###)
- Keine Trennlinien (---, ***)
- {quote_instruction}
- **Fett** zur Hervorhebung von Schlüsselwörtern verwenden, aber keine andere Markdown-Syntax"""

        user_prompt = f"""Interview-Thema: {interview_requirement}

Interview-Inhalt:
{"".join(interview_texts)}

Bitte erstelle eine Interview-Zusammenfassung."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(t("console.generateInterviewSummaryFailed", error=e))
            # Degradieren: Einfache Verkettung
            return f"Insgesamt interviewt: {len(interviews)} Befragte, darunter: " + "、".join([i.agent_name for i in interviews])
