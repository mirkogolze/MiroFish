"""
Dienst zur Erstellung von Ontologien
API 1: Analyse des Textinhalts und Generierung einer Definition für Entitäten und Relationstypen, die für soziale Simulationen geeignet sind.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """Konvertieren beliebiger Formate von Namen in PascalCase (z.B. 'works_for' -> 'WorksFor', 'person' -> 'Person')"""
    # Teile an nicht-alphanumerischen Zeichen
    parts = re.split(r'[^a-zA-Z0-9]+', name)
    # Teile erneut an camelCase-Grenzen (z.B. 'camelCase' -> ['camel', 'Case'])
    words = []
    for part in parts:
        words.extend(re.sub(r'([a-z])([A-Z])', r'\1_\2', part).split('_'))
    # Setze jedes Wort auf Großbuchstaben, filtere leere Zeichen
    result = ''.join(word.capitalize() for word in words if word)
    return result if result else 'Unknown'


# Systemhinweis für Ontologiegenerierung
ONTOLOGY_SYSTEM_PROMPT = """Du bist ein professioneller Experte für Wissensgraph-Ontologie-Design. Deine Aufgabe ist es, gegebene Textinhalte und Simulationsanforderungen zu analysieren und Entitätstypen sowie Beziehungstypen zu entwerfen, die für **Social-Media-Meinungssimulationen** geeignet sind.

**Wichtig: Du musst gültiges JSON-Format ausgeben, keine anderen Inhalte.**

## Kernaufgabe - Hintergrund

Wir bauen ein **Social-Media-Meinungssimulationssystem**. In diesem System:
- Jede Entität ist ein "Account" oder "Akteur", der in sozialen Medien posten, interagieren und Informationen verbreiten kann
- Entitäten beeinflussen sich gegenseitig, teilen, kommentieren und reagieren aufeinander
- Wir müssen die Reaktionen verschiedener Parteien und Informationsverbreitungspfade in Meinungsereignissen simulieren

Daher **müssen Entitäten real existierende Akteure sein, die in sozialen Medien posten und interagieren können**:

**Möglich**:
- Konkrete Einzelpersonen (öffentliche Personen, Beteiligte, Meinungsführer, Experten, normale Menschen)
- Unternehmen (einschließlich ihrer offiziellen Accounts)
- Organisationen (Universitäten, Verbände, NGOs, Gewerkschaften usw.)
- Regierungsbehörden, Aufsichtsbehörden
- Medienorganisationen (Zeitungen, TV-Sender, Blogger, Websites)
- Social-Media-Plattformen selbst
- Vertreter bestimmter Gruppen (z.B. Alumni-Vereine, Fan-Gruppen, Interessenvertretungen)

**Nicht möglich**:
- Abstrakte Konzepte (wie "Meinung", "Stimmung", "Trend")
- Themen/Topics (wie "akademische Integrität", "Bildungsreform")
- Standpunkte/Haltungen (wie "Befürworter", "Gegner")

## Ausgabeformat

Bitte JSON-Format ausgeben mit folgender Struktur:

```json
{
    "entity_types": [
        {
            "name": "Entitätstypname (Englisch, PascalCase)",
            "description": "Kurzbeschreibung (Englisch, max. 100 Zeichen)",
            "attributes": [
                {
                    "name": "Attributname (Englisch, snake_case)",
                    "type": "text",
                    "description": "Attributbeschreibung"
                }
            ],
            "examples": ["Beispielentität 1", "Beispielentität 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Beziehungstypname (Englisch, UPPER_SNAKE_CASE)",
            "description": "Kurzbeschreibung (Englisch, max. 100 Zeichen)",
            "source_targets": [
                {"source": "Quell-Entitätstyp", "target": "Ziel-Entitätstyp"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Kurze Analyse des Textinhalts"
}
```

## Design-Richtlinien (äußerst wichtig!)

### 1. Entitätstyp-Design - Strikte Einhaltung erforderlich

**Mengenanforderung: Exakt 10 Entitätstypen**

**Hierarchie-Anforderung (muss sowohl spezifische als auch Fallback-Typen enthalten)**:

Deine 10 Entitätstypen müssen folgende Ebenen umfassen:

A. **Fallback-Typen (Pflicht, als letzte 2 in der Liste)**:
   - `Person`: Fallback-Typ für jede natürliche Person. Wenn eine Person keinem spezifischeren Personentyp zugeordnet werden kann, wird sie hier eingeordnet.
   - `Organization`: Fallback-Typ für jede Organisation. Wenn eine Organisation keinem spezifischeren Organisationstyp zugeordnet werden kann, wird sie hier eingeordnet.

B. **Spezifische Typen (8 Stück, basierend auf dem Textinhalt)**:
   - Für die Hauptakteure im Text spezifischere Typen entwerfen
   - Beispiel: Bei akademischen Ereignissen: `Student`, `Professor`, `University`
   - Beispiel: Bei geschäftlichen Ereignissen: `Company`, `CEO`, `Employee`

**Warum Fallback-Typen nötig sind**:
- Im Text tauchen verschiedenste Personen auf, wie "Grundschullehrer", "Passant", "ein Internetnutzer"
- Ohne passenden spezifischen Typ werden sie unter `Person` eingeordnet
- Ebenso werden kleine Organisationen, temporäre Gruppen usw. unter `Organization` eingeordnet

**Design-Prinzipien für spezifische Typen**:
- Häufig vorkommende oder zentrale Akteure aus dem Text identifizieren
- Jeder spezifische Typ sollte klare Grenzen haben, Überschneidungen vermeiden
- Description muss klar den Unterschied zum Fallback-Typ erklären

### 2. Beziehungstyp-Design

- Anzahl: 6-10
- Beziehungen sollten reale Verbindungen in Social-Media-Interaktionen widerspiegeln
- Sicherstellen, dass source_targets die definierten Entitätstypen abdecken

### 3. Attribut-Design

- Pro Entitätstyp 1-3 Schlüsselattribute
- **Beachte**: Attributnamen dürfen nicht `name`, `uuid`, `group_id`, `created_at`, `summary` sein (Systemreserviert)
- Empfohlen: `full_name`, `title`, `role`, `position`, `location`, `description` usw.

## Entitätstyp-Referenz

**Personenklasse (spezifisch)**:
- Student: Student
- Professor: Professor/Wissenschaftler
- Journalist: Journalist
- Celebrity: Prominenter/Influencer
- Executive: Führungskraft
- Official: Regierungsbeamter
- Lawyer: Anwalt
- Doctor: Arzt

**Personenklasse (Fallback)**:
- Person: Jede natürliche Person (wenn kein spezifischerer Typ passt)

**Organisationsklasse (spezifisch)**:
- University: Hochschule
- Company: Unternehmen
- GovernmentAgency: Regierungsbehörde
- MediaOutlet: Medienorganisation
- Hospital: Krankenhaus
- School: Schule
- NGO: Nichtregierungsorganisation

**Organisationsklasse (Fallback)**:
- Organization: Jede Organisation (wenn kein spezifischerer Typ passt)

## Beziehungstyp-Referenz

- WORKS_FOR: Arbeitet für
- STUDIES_AT: Studiert an
- AFFILIATED_WITH: Gehört zu
- REPRESENTS: Vertritt
- REGULATES: Reguliert
- REPORTS_ON: Berichtet über
- COMMENTS_ON: Kommentiert
- RESPONDS_TO: Reagiert auf
- SUPPORTS: Unterstützt
- OPPOSES: Lehnt ab
- COLLABORATES_WITH: Kooperiert mit
- COMPETES_WITH: Konkurriert mit
"""


class OntologyGenerator:
    """
Ontologie-Generator
Analyse des Textinhalts zur Generierung von Entitäten und Relationstypen.
"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
Generiert eine Ontologie-Definition

Args:
document_texts: Liste von Dokumententexten
simulation_requirement: Beschreibung der Simulationsanforderungen
additional_context: zusätzlicher Kontext

Returns:
eine Ontologie-Definition (entity_types, edge_types usw.)
"""
        # Erzeuge Benutzer-Nachrichten
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        lang_instruction = get_language_instruction()
        system_prompt = f"{ONTOLOGY_SYSTEM_PROMPT}\n\n{lang_instruction}\nIMPORTANT: Entity type names MUST be in English PascalCase (e.g., 'PersonEntity', 'MediaOrganization'). Relationship type names MUST be in English UPPER_SNAKE_CASE (e.g., 'WORKS_FOR'). Attribute names MUST be in English snake_case. Only description fields and analysis_summary should use the specified language above."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Rufe LLM auf
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=None
        )
        
        # Überprüfe und nachbearbeite
        result = self._validate_and_process(result)
        
        return result
    
    # Maximale Textlänge für LLM (50.000 Zeichen)
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """Erzeuge Benutzer-Nachrichten"""
        
        # Kombiniere Texte
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # Wenn der Text über 50.000 Zeichen geht, kürze (nur für LLM-Inhalt, nicht für Graphenbau)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(Originaltext insgesamt {original_length} Zeichen, gekürzt auf die ersten {self.MAX_TEXT_LENGTH_FOR_LLM} Zeichen für Ontologie-Analyse)..."
        
        message = f"""## Simulationsanforderung

{simulation_requirement}

## Dokumentinhalt

{combined_text}
"""
        
        if additional_context:
            message += f"""
## Zusätzliche Hinweise

{additional_context}
"""
        
        message += """
Basierend auf den obigen Informationen sollst du die passenden Entitätstypen und Beziehungen für eine Simulation der öffentlichen Meinung entwickeln.

**Regeln, die eingehalten werden müssen**:
1. Es muss genau 10 Entitätstypen ausgegeben werden.
2. Die letzten beiden Typen müssen Sicherheitsfalle sein: Person (Sicherheit für Individuen) und Organisation (Sicherheit für Organisationen).
3. Die ersten acht sind spezifische Typen, die auf den Inhalt des Textes basieren.
4. Alle Entitätstypen müssen real existierende Akteure sein, die eine Stimme haben können; abstrakte Konzepte sind nicht zulässig.
5. Eigenschaftsnamen dürfen keine reservierten Wörter wie name, uuid oder group_id verwenden; stattdessen soll man full_name oder org_name verwenden."""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validierung und Nachbearbeitung der Ergebnisse"""
        
        # Stelle sicher, dass notwendige Felder vorhanden sind
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # Überprüfe Entitätstypen
        # Speichere Originalnamen-PascalCase-Abbildung für spätere Korrektur von edge source_targets
        entity_name_map = {}
        for entity in result["entity_types"]:
            # Erzwinge Umwandlung des Entität-Namens in PascalCase (Zep API-Anforderung)
            if "name" in entity:
                original_name = entity["name"]
                entity["name"] = _to_pascal_case(original_name)
                if entity["name"] != original_name:
                    logger.warning(f"Entity type name '{original_name}' auto-converted to '{entity['name']}'")
                entity_name_map[original_name] = entity["name"]
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # Stelle sicher, dass die Beschreibung nicht mehr als 100 Zeichen hat
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # Überprüfe Relationstypen
        for edge in result["edge_types"]:
            # Erzwinge Umwandlung des Kanten-Namens in SCREAMING_SNAKE_CASE (Zep API-Anforderung)
            if "name" in edge:
                original_name = edge["name"]
                edge["name"] = original_name.upper()
                if edge["name"] != original_name:
                    logger.warning(f"Edge type name '{original_name}' auto-converted to '{edge['name']}'")
            # Korrigiere Entität-Referenzen in source_targets, um Übereinstimmung mit PascalCase zu gewährleisten
            for st in edge.get("source_targets", []):
                if st.get("source") in entity_name_map:
                    st["source"] = entity_name_map[st["source"]]
                if st.get("target") in entity_name_map:
                    st["target"] = entity_name_map[st["target"]]
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API-Grenzwerte: maximal 10 benutzerdefinierte Entitätstypen, maximal 10 benutzerdefinierte Kanten-Typen
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # Entferne Duplikate nach name
        seen_names = set()
        deduped = []
        for entity in result["entity_types"]:
            name = entity.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                deduped.append(entity)
            elif name in seen_names:
                logger.warning(f"Duplicate entity type '{name}' removed during validation")
        result["entity_types"] = deduped

        # Fallback-Typendefinition
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # Überprüfe, ob bereits Fallback-Typen vorhanden sind
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # Falls notwendig, füge Fallback-Typen hinzu
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # Wenn hinzugefügt wird und die Grenze von 10 überschritten würde, entferne einige der bestehenden Typen
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # Berechne, wie viele Typen entfernt werden müssen
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # Entferne von hinten (behalte die wichtigeren Typen vorne)
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # Füge einen sicheren Typ hinzu
            result["entity_types"].extend(fallbacks_to_add)
        
        # Stelle sicher, dass die Grenze nicht überschritten wird (defensive Programmierung)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
Konvertiert die Ontologie-Definition in Python-Code (ähnlich ontology.py)

Args:
ontology: Ontologie-Definition

Returns:
einen String mit Python-Code.
"""
        code_lines = [
            '"""',
            'Definition von benutzerdefinierten Entitätstypen',
            'Von MiroFish generiert, für die Simulation sozialer Meinungen verwendet',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== Entitätstypen-Definition ==============',
            '',
        ]
        
        # Generiere Entitätstypen
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== Relationentypen-Definition ==============')
        code_lines.append('')
        
        # Generiere Relationstypen
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # Konvertiere in PascalCase-Klassenname
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # Generiere Typendictionary
        code_lines.append('# ============== Typkonfiguration ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # Generiere Quelle-Ziel-Abbildung für Kanten
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)

