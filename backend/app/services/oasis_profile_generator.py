"""
OASIS Agent-Profil-Generator
Wandelt Zep-Graph-Entitäten in OASIS Agent-Profile um

Optimierungen:
1. Zep-Retrieval für erweiterte Knoten-Informationen
2. Optimierte Prompts für detaillierte Personas
3. Unterscheidung Einzel- vs. Gruppen-Entitäten
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, get_locale, set_locale, t
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent-Profil Datenstruktur"""
    # Allgemeine Felder
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # Optionale Felder - Reddit-Stil
    karma: int = 1000
    
    # Optionale Felder - Twitter-Stil
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # Zusätzliche Persona-Infos
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # Quell-Entitäts-Info
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """In Reddit-Format konvertieren"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS erwartet 'username' (ohne Unterstrich)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # Zusätzliche Persona-Infos hinzufügen
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """In Twitter-Format konvertieren"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS erwartet 'username' (ohne Unterstrich)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # Zusätzliche Persona-Infos hinzufügen
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """In vollständiges Dict-Format konvertieren"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profil-Generator
    
    Wandelt Zep-Graph-Entitäten in OASIS Agent-Profile um
    
    Optimierungen:
    1. Zep-Graph-Retrieval für reicheren Kontext
    2. Sehr detaillierte Personas (Basics, Beruf, Charakter, Social-Media-Verhalten)
    3. Unterscheidung Einzel- vs. Gruppen-Entitäten
    """
    
    # MBTI-Typen
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # Häufige Länder
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # Einzelperson-Entitäten (konkrete Persona)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # Gruppen-/Organisations-Entitäten (repräsentative Persona)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY nicht konfiguriert")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Zep-Client für erweiterten Kontext
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep-Client-Initialisierung fehlgeschlagen: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        OASIS Agent-Profil aus Zep-Entität generieren
        
        Args:
            entity: Zep-Entitätsknoten
            user_id: Nutzer-ID (für OASIS)
            use_llm: LLM für detaillierte Persona
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # Basis-Infos
        name = entity.name
        user_name = self._generate_username(name)
        
        # Kontext aufbauen
        context = self._build_entity_context(entity)
        
        if use_llm:
            # LLM für detaillierte Persona
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # Regelbasierte Basis-Persona
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """Nutzernamen generieren"""
        # Sonderzeichen entfernen, Kleinschreibung
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # Zufallssuffix gegen Duplikate
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        Zep-Graph Hybrid-Search für reichere Entitäts-Infos
        
        Zep hat keine eingebaute Hybrid-Search — Edges und Nodes separat suchen, dann mergen.
        Parallele Requests für Effizienz.
        
        Args:
            entity: Entitätsknoten-Objekt
            
        Returns:
            Dict mit facts, node_summaries, context
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # graph_id erforderlich für Suche
        if not self.graph_id:
            logger.debug(f"Zep-Retrieval übersprungen: kein graph_id")
            return results
        
        comprehensive_query = t('progress.zepSearchQuery', name=entity_name)
        
        def search_edges():
            """Edges suchen (Fakten/Beziehungen) - mit Retry"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep Edge-Suche Versuch {attempt + 1}  Versuch(e) fehlgeschlagen: {str(e)[:80]}, retry...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep Edge-Suche nach {max_retries}  Versuche fehlgeschlagen: {e}")
            return None
        
        def search_nodes():
            """Nodes suchen (Entitäts-Zusammenfassungen) - mit Retry"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep Node-Suche Versuch {attempt + 1}  Versuch(e) fehlgeschlagen: {str(e)[:80]}, retry...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep Node-Suche nach {max_retries}  Versuche fehlgeschlagen: {e}")
            return None
        
        try:
            # Edges und Nodes parallel suchen
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # Ergebnisse abrufen
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # Edge-Suchergebnisse verarbeiten
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # Node-Suchergebnisse verarbeiten
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"Verwandte Entität: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # Gesamtkontext aufbauen
            context_parts = []
            if results["facts"]:
                context_parts.append("Fakten:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("Verwandte Entität:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep Hybrid-Retrieval abgeschlossen: {entity_name}, abrufen {len(results['facts'])}  Fakten, {len(results['node_summaries'])}  verwandte Knoten")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep-Retrieval Timeout ({entity_name})")
        except Exception as e:
            logger.warning(f"Zep-Retrieval fehlgeschlagen ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        Vollständigen Entitätskontext aufbauen
        
        Enthält:
        1. Entitäts-Edges (Fakten)
        2. Verwandte Knoten-Details
        3. Zep Hybrid-Retrieval Ergebnisse
        """
        context_parts = []
        
        # 1. Entitäts-Attribute
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### Entitäts-Attribute\n" + "\n".join(attrs))
        
        # 2. Verwandte Edges (Fakten/Beziehungen)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # ohne Limit
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (Verwandte Entität)")
                    else:
                        relationships.append(f"- (Verwandte Entität) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### Verwandte Fakten und Beziehungen\n" + "\n".join(relationships))
        
        # 3. Verwandte Knoten-Details
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # ohne Limit
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # Standard-Labels filtern
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### Verwandte Entitäten\n" + "\n".join(related_info))
        
        # 4. Zep Hybrid-Retrieval
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # Deduplizierung
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep-Retrieval: Fakten\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep-Retrieval: Verwandte Knoten\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """Prüft ob Einzelperson-Entität"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """Prüft ob Gruppen-/Organisations-Entität"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Detaillierte Persona via LLM generieren
        
        Nach Entitätstyp unterschieden:
        - Einzelperson: konkrete Persona
        - Gruppe/Organisation: repräsentative Account-Persona
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # Mehrere Versuche bis Erfolg oder Max-Retries
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # Temperatur pro Retry senken
                    # Kein max_tokens, LLM frei generieren lassen
                )
                
                content = response.choices[0].message.content
                
                # Prüfen ob abgeschnitten (finish_reason != stop)
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLM-Output abgeschnitten (attempt {attempt+1}), versuche Reparatur...")
                    content = self._fix_truncated_json(content)
                
                # JSON parsen versuchen
                try:
                    result = json.loads(content)
                    
                    # Pflichtfelder validieren
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name} ist ein/e {entity_type}。"
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON-Parsing fehlgeschlagen (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # versuche ReparaturJSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLM-Aufruf fehlgeschlagen (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # Exponential Backoff
        
        logger.warning(f"LLM-Persona-Generierung fehlgeschlagen（{max_attempts} Versuche): {last_error}, nutze regelbasierte Generierung")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """Abgeschnittenes JSON reparieren"""
        import re
        
        # Abgeschnittenes JSON schließen
        content = content.strip()
        
        # Offene Klammern zählen
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # Offene Strings prüfen
        # Einfacher Check: String evtl. abgeschnitten
        if content and content[-1] not in '",}]':
            # String schließen
            content += '"'
        
        # Klammern schließen
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """Beschädigtes JSON reparieren"""
        import re
        
        # 1. Abgeschnittenes reparieren
        content = self._fix_truncated_json(content)
        
        # 2. JSON-Teil extrahieren
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. Zeilenumbrüche in Strings behandeln
            # Zeilenumbrüche in String-Werten ersetzen
            def fix_string_newlines(match):
                s = match.group(0)
                # Echte Zeilenumbrüche durch Leerzeichen ersetzen
                s = s.replace('\n', ' ').replace('\r', ' ')
                # Überflüssige Leerzeichen entfernen
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # JSON-String-Werte matchen
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. Parsen versuchen
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. Aggressivere Reparatur
                try:
                    # Steuerzeichen entfernen
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # Aufeinanderfolgende Whitespaces ersetzen
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. Teil-Informationen extrahieren
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # evtl. abgeschnitten
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name} ist ein/e {entity_type}。")
        
        # Bei sinnvollem Inhalt als repariert markieren
        if bio_match or persona_match:
            logger.info(f"Teil-Informationen aus beschädigtem JSON extrahiert")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. Komplett fehlgeschlagen, Basis-Struktur zurückgeben
        logger.warning(f"JSON-Reparatur fehlgeschlagen, Basis-Struktur")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} ist ein/e {entity_type}。"
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """Get system prompt"""
        base_prompt = "Du bist ein Experte für Social-Media-Nutzerprofile. Erstelle detaillierte, realistische Personas für Meinungssimulationen, die die bestehende Realität möglichst genau abbilden. Du musst gültiges JSON-Format zurückgeben, alle String-Werte dürfen keine unescapeten Zeilenumbrüche enthalten."
        return f"{base_prompt}\n\n{get_language_instruction()}"
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Persona-Prompt für Einzelperson-Entität"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "keine"
        context_str = context[:3000] if context else "kein zusätzlicher Kontext"
        
        return f"""Erstelle ein detailliertes Social-Media-Nutzerprofil für diese Entität, das die bestehende Realität möglichst genau abbildet.

Entitätsname: {entity_name}
Entitätstyp: {entity_type}
Entitätszusammenfassung: {entity_summary}
Entitätsattribute: {attrs_str}

Kontextinformationen:
{context_str}

Bitte generiere JSON mit folgenden Feldern:

1. bio: Social-Media-Kurzbiografie, 200 Zeichen
2. persona: Detaillierte Persona-Beschreibung (2000 Zeichen Fließtext), muss enthalten:
   - Basisinformationen (Alter, Beruf, Bildungshintergrund, Standort)
   - Hintergrund (wichtige Erfahrungen, Verbindung zum Ereignis, soziale Beziehungen)
   - Persönlichkeitsmerkmale (MBTI-Typ, Kerncharakter, emotionaler Ausdruck)
   - Social-Media-Verhalten (Posting-Frequenz, Inhaltspräferenzen, Interaktionsstil, Sprachmerkmale)
   - Standpunkte (Haltung zu Themen, was sie provoziert/berührt)
   - Besondere Merkmale (Redewendungen, besondere Erfahrungen, Hobbys)
   - Persönliche Erinnerungen (wichtiger Teil der Persona, Verbindung zum Ereignis, bisherige Aktionen und Reaktionen)
3. age: Alter als Zahl (muss Ganzzahl sein)
4. gender: Geschlecht, muss englisch sein: "male" oder "female"
5. mbti: MBTI-Typ (z.B. INTJ, ENFP etc.)
6. country: Land
7. profession: Beruf
8. interested_topics: Array mit Interessensthemen

Wichtig:
- Alle Feldwerte müssen Strings oder Zahlen sein, keine Zeilenumbrüche verwenden
- persona muss ein zusammenhängender Fließtext sein
- {get_language_instruction()} (gender-Feld muss englisch male/female sein)
- Inhalte müssen mit den Entitätsinformationen konsistent sein
- age muss eine gültige Ganzzahl sein, gender muss "male" oder "female" sein
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Persona-Prompt für Gruppen-/Organisations-Entität"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "keine"
        context_str = context[:3000] if context else "kein zusätzlicher Kontext"
        
        return f"""Erstelle eine detaillierte Social-Media-Kontoeinstellung für diese Institutions-/Gruppen-Entität, die die bestehende Realität möglichst genau abbildet.

Entitätsname: {entity_name}
Entitätstyp: {entity_type}
Entitätszusammenfassung: {entity_summary}
Entitätsattribute: {attrs_str}

Kontextinformationen:
{context_str}

Bitte generiere JSON mit folgenden Feldern:

1. bio: Offizielle Kontokurzbiografie, 200 Zeichen, professionell und angemessen
2. persona: Detaillierte Kontobeschreibung (2000 Zeichen Fließtext), muss enthalten:
   - Basisinformationen der Institution (offizieller Name, Art der Institution, Gründungshintergrund, Hauptfunktionen)
   - Kontopositionierung (Kontotyp, Zielgruppe, Kernfunktionen)
   - Kommunikationsstil (Sprachmerkmale, häufige Ausdrücke, Tabuthemen)
   - Inhaltsmerkmale (Inhaltstypen, Veröffentlichungsfrequenz, aktive Zeiträume)
   - Standpunkte (offizielle Position zu Kernthemen, Umgang mit Kontroversen)
   - Besonderheiten (Gruppenprofil das vertreten wird, Betriebsgewohnheiten)
   - Institutionelles Gedächtnis (wichtiger Teil der Persona, Verbindung zum Ereignis, bisherige Aktionen und Reaktionen)
3. age: Fest 30 (virtuelles Alter des Institutionskontos)
4. gender: Fest "other" (Institutionskonto verwendet other für nicht-persönlich)
5. mbti: MBTI-Typ zur Beschreibung des Kontostils, z.B. ISTJ für streng-konservativ
6. country: Land
7. profession: Beschreibung der Institutionsfunktion
8. interested_topics: Array mit Interessenbereichen

Wichtig:
- Alle Feldwerte müssen Strings oder Zahlen sein, keine null-Werte
- persona muss ein zusammenhängender Fließtext sein, keine Zeilenumbrüche
- {get_language_instruction()} (gender-Feld muss englisch "other" sein)
- age muss Ganzzahl 30 sein, gender muss String "other" sein
- Institutionskonto-Kommunikation muss der Identitätspositionierung entsprechen"""
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Regelbasierte Basis-Persona generieren"""
        
        # Persona nach Entitätstyp
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # virtuelles Alter (Organisation)
                "gender": "other",  # Organisation = other
                "mbti": "ISTJ",  # Org-Stil: streng, konservativ
                "country": "Deutschland",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # virtuelles Alter (Organisation)
                "gender": "other",  # Organisation = other
                "mbti": "ISTJ",  # Org-Stil: streng, konservativ
                "country": "Deutschland",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # Standard-Persona
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """Graph-ID für Zep-Retrieval setzen"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        Batch Agent-Profile aus Entitäten generieren (parallel)
        
        Args:
            entities: Entitäten-Liste
            use_llm: LLM für detaillierte Persona
            progress_callback: Fortschritts-Callback (current, total, message)
            graph_id: Graph-ID für Zep-Retrieval
            parallel_count: Parallelität, Standard 5
            realtime_output_path: Echtzeit-Output-Pfad (jedes Profil sofort schreiben)
            output_platform: Plattform-Format ("reddit" oder "twitter")
            
        Returns:
            Agent-Profil-Liste
        """
        import concurrent.futures
        from threading import Lock
        
        # Graph-ID für Zep-Retrieval setzen
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # vorab allokiert für Reihenfolge
        completed_count = [0]  # Liste für Closure-Zugriff
        lock = Lock()
        
        # Hilfsfunktion: Echtzeit-Datei-Schreiben
        def save_profiles_realtime():
            """Generierte Profile in Echtzeit speichern"""
            if not realtime_output_path:
                return
            
            with lock:
                # Fertige Profile filtern
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON-Format
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV-Format
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"Echtzeit-Speichern fehlgeschlagen: {e}")
        
        # Capture locale before spawning thread pool workers
        current_locale = get_locale()

        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """Worker: Einzelnes Profil generieren"""
            set_locale(current_locale)
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # Persona in Konsole/Log ausgeben
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"Entität {entity.name}  Persona-Generierung fehlgeschlagen: {str(e)}")
                # Basis-Profil erstellen
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"Parallele Generierung starten: {total}  Agent-Personas (Parallelität: {parallel_count}）...")
        print(f"\n{'='*60}")
        print(f"Agent-Persona-Generierung starten - {total}  Entitäten, Parallelität: {parallel_count}")
        print(f"{'='*60}\n")
        
        # Thread-Pool parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # Alle Tasks einreichen
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # Ergebnisse sammeln
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # Echtzeit in Datei schreiben
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"Abgeschlossen {current}/{total}: {entity.name}（{entity_type}）"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} Fallback-Persona verwendet: {error}")
                    else:
                        logger.info(f"[{current}/{total}] Persona erfolgreich generiert: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"Entität {entity.name}  Exception aufgetreten: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # Echtzeit in Datei schreiben(auch bei Fallback)
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"Persona-Generierung abgeschlossen! Generiert: {len([p for p in profiles if p])}  Agents")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """Persona-Output in Konsole (vollständig)"""
        separator = "-" * 70
        
        # Vollständiger Output (ungekürzt)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'keine'
        
        output_lines = [
            f"\n{separator}",
            t('progress.profileGenerated', name=entity_name, type=entity_type),
            f"{separator}",
            f"Nutzername: {profile.user_name}",
            f"",
            f"【Kurzprofil】",
            f"{profile.bio}",
            f"",
            f"【Detaillierte Persona】",
            f"{profile.persona}",
            f"",
            f"【Basis-Attribute】",
            f"Alter: {profile.age} | Geschlecht: {profile.gender} | MBTI: {profile.mbti}",
            f"Beruf: {profile.profession} | Land: {profile.country}",
            f"Interessen: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # Nur Konsole (Logger gibt nicht mehr Volltext aus)
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        Profile in Datei speichern (plattformspezifisches Format)
        
        OASIS-Plattform-Formate:
        - Twitter: CSV-Format
        - Reddit: JSON-Format
        
        Args:
            profiles: Profil-Liste
            file_path: Dateipfad
            platform: Plattformtyp ("reddit" oder "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Twitter-Profile als CSV speichern (OASIS-konform)
        
        OASIS Twitter CSV-Felder:
        - user_id: Nutzer-ID (ab 0)
        - name: Echter Name
        - username: System-Nutzername
        - user_char: Detaillierte Persona (LLM System-Prompt, steuert Agent-Verhalten)
        - description: Kurze öffentliche Bio (Profilseite)
        
        user_char vs description Unterschied:
        - user_char: intern, LLM System-Prompt, bestimmt Agent-Denken/Handeln
        - description: extern sichtbar, öffentliche Bio
        """
        import csv
        
        # .csv-Erweiterung sicherstellen
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # OASIS-Header schreiben
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # Datenzeilen schreiben
            for idx, profile in enumerate(profiles):
                # user_char: Vollständige Persona (bio + persona) für LLM System-Prompt
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # Zeilenumbrüche ersetzen (CSV braucht Leerzeichen)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: Kurze Bio, extern sichtbar
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: sequenziell ab 0
                    profile.name,           # name: Echter Name
                    profile.user_name,      # username: Nutzername
                    user_char,              # user_char: Vollständige Persona (intern für LLM)
                    description             # description: Kurze Bio (extern)
                ]
                writer.writerow(row)
        
        logger.info(f"Gespeichert: {len(profiles)}  Twitter-Profile gespeichert in {file_path} (OASIS CSV-Format)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        Gender-Feld auf OASIS-Format normalisieren (EN)
        
        OASIS erwartet: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # Chinesisch-Mapping (Legacy)
        gender_map = {
            "男": "male",
            "女": "female",
            "机构": "other",
            "其他": "other",
            # Englisch bereits OK
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Reddit-Profile als JSON speichern
        
        Format konsistent mit to_reddit_format(), damit OASIS korrekt liest.
        user_id ist Pflicht — OASIS agent_graph.get_agent() matcht darüber!
        
        Pflichtfelder:
        - user_id: Nutzer-ID (int, matcht poster_agent_id in initial_posts)
        - username: Nutzername
        - name: Anzeigename
        - bio: Kurzprofil
        - persona: Detaillierte Persona
        - age: Alter (int)
        - gender: "male", "female", oder "other"
        - mbti: MBTI-Typ
        - country: Land
        """
        data = []
        for idx, profile in enumerate(profiles):
            # Format konsistent mit to_reddit_format()
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # Pflicht: user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS-Pflichtfelder mit Defaults
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "Deutschland",
            }
            
            # Optionale Felder
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Gespeichert: {len(profiles)}  Reddit-Profile gespeichert in {file_path} (JSON-Format, mit user_id)")
    
    # Alte Methode als Alias (Rückwärtskompatibilität)
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[Deprecated] Bitte save_profiles() verwenden"""
        logger.warning("save_profiles_to_json ist deprecated, bitte save_profiles verwenden")
        self.save_profiles(profiles, file_path, platform)

