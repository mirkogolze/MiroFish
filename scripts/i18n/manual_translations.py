"""
Manual translations for the 43 segments that failed LLM translation.
These are mostly long docstrings and LLM prompts from report.py, simulation.py, 
report_agent.py, simulation_config_generator.py.
"""
import json

translations = [
    {
        "id": "backend/app/api/report.py:474:4:STRING",
        "kind": "docstring",
        "translation": "\n    Mit dem Report Agent kommunizieren\n    \n    Der Report Agent kann im Gespräch eigenständig Retrieval-Tools aufrufen, um Fragen zu beantworten\n    \n    Anfrage (JSON):\n        {\n            \"simulation_id\": \"sim_xxxx\",        // Pflicht, Simulations-ID\n            \"message\": \"Bitte erkläre den Meinungstrend\",    // Pflicht, Benutzernachricht\n            \"chat_history\": [                   // Optional, Gesprächsverlauf\n                {\"role\": \"user\", \"content\": \"...\"},\n                {\"role\": \"assistant\", \"content\": \"...\"}\n            ]\n        }\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"response\": \"Agent-Antwort...\",\n                \"tool_calls\": [Liste der aufgerufenen Tools],\n                \"sources\": [Informationsquellen]\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:571:4:STRING",
        "kind": "docstring",
        "translation": "\n    Berichterstellungs-Fortschritt abrufen (Echtzeit)\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"status\": \"generating\",\n                \"progress\": 45,\n                \"message\": \"Kapitel wird generiert: Wichtige Erkenntnisse\",\n                \"current_section\": \"Wichtige Erkenntnisse\",\n                \"completed_sections\": [\"Executive Summary\", \"Simulationshintergrund\"],\n                \"updated_at\": \"2025-12-09T...\"\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:663:4:STRING",
        "kind": "docstring",
        "translation": "\n    Einzelnes Kapitel abrufen\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"filename\": \"section_01.md\",\n                \"content\": \"## Executive Summary\\\\n\\\\n...\"\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:760:4:STRING",
        "kind": "docstring",
        "translation": "\n    Detailliertes Ausführungsprotokoll des Report Agent abrufen\n    \n    Echtzeit-Abruf jedes einzelnen Schritts während der Berichterstellung, einschließlich:\n    - Berichtstart, Planungsbeginn/-abschluss\n    - Start, Tool-Aufrufe, LLM-Antworten und Abschluss jedes Kapitels\n    - Berichtfertigstellung oder -fehler\n    \n    Query-Parameter:\n        from_line: Ab welcher Zeile gelesen wird (optional, Standard 0, für inkrementellen Abruf)\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"logs\": [\n                    {\n                        \"timestamp\": \"2025-12-13T...\",\n                        \"elapsed_seconds\": 12.5,\n                        \"report_id\": \"report_xxxx\",\n                        \"action\": \"tool_call\",\n                        \"stage\": \"generating\",\n                        \"section_title\": \"Executive Summary\",\n                        \"section_index\": 1,\n                        \"details\": {\n                            \"tool_name\": \"insight_forge\",\n                            \"parameters\": {...},\n                            ...\n                        }\n                    },\n                    ...\n                ],\n                \"total_lines\": 25,\n                \"from_line\": 0,\n                \"has_more\": false\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:819:4:STRING",
        "kind": "docstring",
        "translation": "\n    Vollständiges Agent-Protokoll abrufen (alles auf einmal)\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"logs\": [...],\n                \"count\": 25\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:855:4:STRING",
        "kind": "docstring",
        "translation": "\n    Konsolenausgabe-Protokoll des Report Agent abrufen\n    \n    Echtzeit-Abruf der Konsolenausgaben (INFO, WARNING usw.) während der Berichterstellung.\n    Dies unterscheidet sich vom strukturierten JSON-Protokoll der agent-log-Schnittstelle;\n    es handelt sich um Protokolle im reinen Textformat im Konsolenstil.\n    \n    Query-Parameter:\n        from_line: Ab welcher Zeile gelesen wird (optional, Standard 0, für inkrementellen Abruf)\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"logs\": [\n                    \"[19:46:14] INFO: Suche abgeschlossen: 15 relevante Fakten gefunden\",\n                    \"[19:46:14] INFO: Graph-Suche: graph_id=xxx, query=...\",\n                    ...\n                ],\n                \"total_lines\": 100,\n                \"from_line\": 0,\n                \"has_more\": false\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:901:4:STRING",
        "kind": "docstring",
        "translation": "\n    Vollständiges Konsolenprotokoll abrufen (alles auf einmal)\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"logs\": [...],\n                \"count\": 100\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:937:4:STRING",
        "kind": "docstring",
        "translation": "\n    Graph-Such-Tool-Schnittstelle (für Debugging)\n    \n    Anfrage (JSON):\n        {\n            \"graph_id\": \"mirofish_xxxx\",\n            \"query\": \"Suchanfrage\",\n            \"limit\": 10\n        }\n    "
    },
    {
        "id": "backend/app/api/report.py:985:4:STRING",
        "kind": "docstring",
        "translation": "\n    Graph-Statistik-Tool-Schnittstelle (für Debugging)\n    \n    Anfrage (JSON):\n        {\n            \"graph_id\": \"mirofish_xxxx\"\n        }\n    "
    },
    {
        "id": "backend/app/api/simulation.py:29:4:STRING",
        "kind": "docstring",
        "translation": "\n    Interview-Frage optimieren, Präfix hinzufügen um Tool-Aufrufe durch den Agent zu vermeiden\n    \n    Args:\n        prompt: Ursprüngliche Frage\n        \n    Returns:\n        Optimierte Frage\n    "
    },
    {
        "id": "backend/app/api/simulation.py:167:4:STRING",
        "kind": "docstring",
        "translation": "\n    Neue Simulation erstellen\n    \n    Hinweis: Parameter wie max_rounds werden intelligent vom LLM generiert, keine manuelle Einstellung nötig\n    \n    Anfrage (JSON):\n        {\n            \"project_id\": \"proj_xxxx\",      // Pflicht\n            \"graph_id\": \"mirofish_xxxx\",    // Optional, wird sonst aus dem Projekt abgerufen\n            \"enable_twitter\": true,          // Optional, Standard true\n            \"enable_reddit\": true            // Optional, Standard true\n        }\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"simulation_id\": \"sim_xxxx\",\n                \"project_id\": \"proj_xxxx\",\n                \"graph_id\": \"mirofish_xxxx\",\n                \"status\": \"created\",\n                \"enable_twitter\": true,\n                \"enable_reddit\": true,\n                \"created_at\": \"2025-12-01T10:00:00\"\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/simulation.py:1325:4:STRING",
        "kind": "docstring",
        "translation": "\n    Simulations-Laufskript herunterladen (generisches Skript, unter backend/scripts/)\n    \n    Mögliche Werte für script_name:\n        - run_twitter_simulation.py\n        - run_reddit_simulation.py\n        - run_parallel_simulation.py\n        - action_logger.py\n    "
    },
    {
        "id": "backend/app/api/simulation.py:1379:4:STRING",
        "kind": "docstring",
        "translation": "\n    OASIS Agent Profile direkt aus dem Graphen generieren (ohne Simulation zu erstellen)\n    \n    Anfrage (JSON):\n        {\n            \"graph_id\": \"mirofish_xxxx\",     // Pflicht\n            \"entity_types\": [\"Student\"],      // Optional\n            \"use_llm\": true,                  // Optional\n            \"platform\": \"reddit\"              // Optional\n        }\n    "
    },
    {
        "id": "backend/app/api/simulation.py:1707:4:STRING",
        "kind": "docstring",
        "translation": "\n    Echtzeit-Status der Simulationsausführung abrufen (für Frontend-Polling)\n    \n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"simulation_id\": \"sim_xxxx\",\n                \"runner_status\": \"running\",\n                \"current_round\": 5,\n                \"total_rounds\": 144,\n                \"progress_percent\": 3.5,\n                \"simulated_hours\": 2,\n                \"total_simulation_hours\": 72,\n                \"twitter_running\": true,\n                \"reddit_running\": true,\n                \"twitter_actions_count\": 150,\n                \"reddit_actions_count\": 200,\n                \"total_actions_count\": 350,\n                \"started_at\": \"2025-12-01T10:00:00\",\n                \"updated_at\": \"2025-12-01T10:30:00\"\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/simulation.py:1920:4:STRING",
        "kind": "docstring",
        "translation": "\n    Simulations-Zeitachse abrufen (nach Runden zusammengefasst)\n    \n    Für Frontend-Fortschrittsbalken und Zeitachsen-Ansicht\n    \n    Query-Parameter:\n        start_round: Startrunde (Standard 0)\n        end_round: Endrunde (Standard alle)\n    \n    Gibt zusammengefasste Informationen pro Runde zurück\n    "
    },
    {
        "id": "backend/app/api/simulation.py:1989:4:STRING",
        "kind": "docstring",
        "translation": "\n    Beiträge aus der Simulation abrufen\n    \n    Query-Parameter:\n        platform: Plattformtyp (twitter/reddit)\n        limit: Anzahl der Ergebnisse (Standard 50)\n        offset: Versatz\n    \n    Gibt Beitragsliste zurück (aus SQLite-Datenbank gelesen)\n    "
    },
    {
        "id": "backend/app/api/simulation.py:2514:4:STRING",
        "kind": "docstring",
        "translation": "\n    Interview-Verlauf abrufen\n\n    Liest alle Interview-Einträge aus der Simulationsdatenbank\n\n    Anfrage (JSON):\n        {\n            \"simulation_id\": \"sim_xxxx\",  // Pflicht, Simulations-ID\n            \"platform\": \"reddit\",          // Optional, Plattformtyp (reddit/twitter)\n                                           // Ohne Angabe werden alle Plattformen zurückgegeben\n            \"agent_id\": 0,                 // Optional, nur Interviews dieses Agents abrufen\n            \"limit\": 100                   // Optional, Anzahl der Ergebnisse, Standard 100\n        }\n\n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"count\": 10,\n                \"history\": [\n                    {\n                        \"agent_id\": 0,\n                        \"response\": \"Ich denke...\",\n                        \"prompt\": \"Was halten Sie davon?\",\n                        \"timestamp\": \"2025-12-08T10:00:00\",\n                        \"platform\": \"reddit\"\n                    },\n                    ...\n                ]\n            }\n        }\n    "
    },
    {
        "id": "backend/app/api/simulation.py:2586:4:STRING",
        "kind": "docstring",
        "translation": "\n    Simulationsumgebungsstatus abrufen\n\n    Prüft ob die Simulationsumgebung aktiv ist (Interview-Befehle empfangen kann)\n\n    Anfrage (JSON):\n        {\n            \"simulation_id\": \"sim_xxxx\"  // Pflicht, Simulations-ID\n        }\n\n    Rückgabe:\n        {\n            \"success\": true,\n            \"data\": {\n                \"simulation_id\": \"sim_xxxx\",\n                \"env_alive\": true,\n                \"twitter_available\": true,\n                \"reddit_available\": true,\n                \"message\": \"Umgebung läuft, kann Interview-Befehle empfangen\"\n            }\n        }\n    "
    },
    {
        "id": "backend/app/services/ontology_generator.py:30:25:STRING",
        "kind": "llm_prompt",
        "translation": "Du bist ein professioneller Experte für Wissensgraph-Ontologie-Design. Deine Aufgabe ist es, gegebene Textinhalte und Simulationsanforderungen zu analysieren und Entitätstypen sowie Beziehungstypen zu entwerfen, die für **Social-Media-Meinungssimulationen** geeignet sind.\n\n**Wichtig: Du musst gültiges JSON-Format ausgeben, keine anderen Inhalte.**\n\n## Kernaufgabe - Hintergrund\n\nWir bauen ein **Social-Media-Meinungssimulationssystem**. In diesem System:\n- Jede Entität ist ein \"Account\" oder \"Akteur\", der in sozialen Medien posten, interagieren und Informationen verbreiten kann\n- Entitäten beeinflussen sich gegenseitig, teilen, kommentieren und reagieren aufeinander\n- Wir müssen die Reaktionen verschiedener Parteien und Informationsverbreitungspfade in Meinungsereignissen simulieren\n\nDaher **müssen Entitäten real existierende Akteure sein, die in sozialen Medien posten und interagieren können**:\n\n**Möglich**:\n- Konkrete Einzelpersonen (öffentliche Personen, Beteiligte, Meinungsführer, Experten, normale Menschen)\n- Unternehmen (einschließlich ihrer offiziellen Accounts)\n- Organisationen (Universitäten, Verbände, NGOs, Gewerkschaften usw.)\n- Regierungsbehörden, Aufsichtsbehörden\n- Medienorganisationen (Zeitungen, TV-Sender, Blogger, Websites)\n- Social-Media-Plattformen selbst\n- Vertreter bestimmter Gruppen (z.B. Alumni-Vereine, Fan-Gruppen, Interessenvertretungen)\n\n**Nicht möglich**:\n- Abstrakte Konzepte (wie \"Meinung\", \"Stimmung\", \"Trend\")\n- Themen/Topics (wie \"akademische Integrität\", \"Bildungsreform\")\n- Standpunkte/Haltungen (wie \"Befürworter\", \"Gegner\")\n\n## Ausgabeformat\n\nBitte JSON-Format ausgeben mit folgender Struktur:\n\n```json\n{\n    \"entity_types\": [\n        {\n            \"name\": \"Entitätstypname (Englisch, PascalCase)\",\n            \"description\": \"Kurzbeschreibung (Englisch, max. 100 Zeichen)\",\n            \"attributes\": [\n                {\n                    \"name\": \"Attributname (Englisch, snake_case)\",\n                    \"type\": \"text\",\n                    \"description\": \"Attributbeschreibung\"\n                }\n            ],\n            \"examples\": [\"Beispielentität 1\", \"Beispielentität 2\"]\n        }\n    ],\n    \"edge_types\": [\n        {\n            \"name\": \"Beziehungstypname (Englisch, UPPER_SNAKE_CASE)\",\n            \"description\": \"Kurzbeschreibung (Englisch, max. 100 Zeichen)\",\n            \"source_targets\": [\n                {\"source\": \"Quell-Entitätstyp\", \"target\": \"Ziel-Entitätstyp\"}\n            ],\n            \"attributes\": []\n        }\n    ],\n    \"analysis_summary\": \"Kurze Analyse des Textinhalts\"\n}\n```\n\n## Design-Richtlinien (äußerst wichtig!)\n\n### 1. Entitätstyp-Design - Strikte Einhaltung erforderlich\n\n**Mengenanforderung: Exakt 10 Entitätstypen**\n\n**Hierarchie-Anforderung (muss sowohl spezifische als auch Fallback-Typen enthalten)**:\n\nDeine 10 Entitätstypen müssen folgende Ebenen umfassen:\n\nA. **Fallback-Typen (Pflicht, als letzte 2 in der Liste)**:\n   - `Person`: Fallback-Typ für jede natürliche Person. Wenn eine Person keinem spezifischeren Personentyp zugeordnet werden kann, wird sie hier eingeordnet.\n   - `Organization`: Fallback-Typ für jede Organisation. Wenn eine Organisation keinem spezifischeren Organisationstyp zugeordnet werden kann, wird sie hier eingeordnet.\n\nB. **Spezifische Typen (8 Stück, basierend auf dem Textinhalt)**:\n   - Für die Hauptakteure im Text spezifischere Typen entwerfen\n   - Beispiel: Bei akademischen Ereignissen: `Student`, `Professor`, `University`\n   - Beispiel: Bei geschäftlichen Ereignissen: `Company`, `CEO`, `Employee`\n\n**Warum Fallback-Typen nötig sind**:\n- Im Text tauchen verschiedenste Personen auf, wie \"Grundschullehrer\", \"Passant\", \"ein Internetnutzer\"\n- Ohne passenden spezifischen Typ werden sie unter `Person` eingeordnet\n- Ebenso werden kleine Organisationen, temporäre Gruppen usw. unter `Organization` eingeordnet\n\n**Design-Prinzipien für spezifische Typen**:\n- Häufig vorkommende oder zentrale Akteure aus dem Text identifizieren\n- Jeder spezifische Typ sollte klare Grenzen haben, Überschneidungen vermeiden\n- Description muss klar den Unterschied zum Fallback-Typ erklären\n\n### 2. Beziehungstyp-Design\n\n- Anzahl: 6-10\n- Beziehungen sollten reale Verbindungen in Social-Media-Interaktionen widerspiegeln\n- Sicherstellen, dass source_targets die definierten Entitätstypen abdecken\n\n### 3. Attribut-Design\n\n- Pro Entitätstyp 1-3 Schlüsselattribute\n- **Beachte**: Attributnamen dürfen nicht `name`, `uuid`, `group_id`, `created_at`, `summary` sein (Systemreserviert)\n- Empfohlen: `full_name`, `title`, `role`, `position`, `location`, `description` usw.\n\n## Entitätstyp-Referenz\n\n**Personenklasse (spezifisch)**:\n- Student: Student\n- Professor: Professor/Wissenschaftler\n- Journalist: Journalist\n- Celebrity: Prominenter/Influencer\n- Executive: Führungskraft\n- Official: Regierungsbeamter\n- Lawyer: Anwalt\n- Doctor: Arzt\n\n**Personenklasse (Fallback)**:\n- Person: Jede natürliche Person (wenn kein spezifischerer Typ passt)\n\n**Organisationsklasse (spezifisch)**:\n- University: Hochschule\n- Company: Unternehmen\n- GovernmentAgency: Regierungsbehörde\n- MediaOutlet: Medienorganisation\n- Hospital: Krankenhaus\n- School: Schule\n- NGO: Nichtregierungsorganisation\n\n**Organisationsklasse (Fallback)**:\n- Organization: Jede Organisation (wenn kein spezifischerer Typ passt)\n\n## Beziehungstyp-Referenz\n\n- WORKS_FOR: Arbeitet für\n- STUDIES_AT: Studiert an\n- AFFILIATED_WITH: Gehört zu\n- REPRESENTS: Vertritt\n- REGULATES: Reguliert\n- REPORTS_ON: Berichtet über\n- COMMENTS_ON: Kommentiert\n- RESPONDS_TO: Reagiert auf\n- SUPPORTS: Unterstützt\n- OPPOSES: Lehnt ab\n- COLLABORATES_WITH: Kooperiert mit\n- COMPETES_WITH: Konkurriert mit\n"
    },
    {
        "id": "backend/app/services/report_agent.py:37:4:STRING",
        "kind": "docstring",
        "translation": "\n    Report Agent Detailprotokoll-Recorder\n    \n    Erzeugt eine agent_log.jsonl-Datei im Berichtsordner, die jeden einzelnen Schritt detailliert protokolliert.\n    Jede Zeile ist ein vollständiges JSON-Objekt mit Zeitstempel, Aktionstyp, detailliertem Inhalt usw.\n    "
    },
    {
        "id": "backend/app/services/report_agent.py:75:8:STRING",
        "kind": "docstring",
        "translation": "\n        Einen Protokolleintrag schreiben\n        \n        Args:\n            action: Aktionstyp, z.B. 'start', 'tool_call', 'llm_response', 'section_complete' usw.\n            stage: Aktuelle Phase, z.B. 'planning', 'generating', 'completed'\n            details: Detail-Dictionary, ungekürzt\n            section_title: Aktueller Kapiteltitel (optional)\n            section_index: Aktueller Kapitelindex (optional)\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:264:8:STRING",
        "kind": "docstring",
        "translation": "\n        Kapitelgenerierung als abgeschlossen protokollieren\n\n        Das Frontend sollte dieses Protokoll überwachen, um festzustellen, ob ein Kapitel wirklich fertig ist, und den vollständigen Inhalt abzurufen\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:316:8:STRING",
        "kind": "docstring",
        "translation": "\n        Konsolen-Logger initialisieren\n        \n        Args:\n            report_id: Bericht-ID, bestimmt den Protokolldateipfad\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:494:28:STRING",
        "kind": "docstring",
        "translation": "\\\n【Breitensuche - Gesamtübersicht erhalten】\nDieses Tool dient dazu, einen vollständigen Überblick über die Simulationsergebnisse zu erhalten, besonders geeignet um den Verlauf von Ereignissen zu verstehen. Es:\n1. Ruft alle relevanten Knoten und Beziehungen ab\n2. Unterscheidet zwischen aktuell gültigen Fakten und historischen/veralteten Fakten\n3. Hilft zu verstehen, wie sich die Meinung entwickelt hat\n\n【Einsatzszenarien】\n- Vollständigen Entwicklungsverlauf eines Ereignisses verstehen\n- Meinungsänderungen verschiedener Phasen vergleichen\n- Umfassende Entitäts- und Beziehungsinformationen erhalten\n\n【Rückgabe-Inhalt】\n- Aktuell gültige Fakten (neueste Simulationsergebnisse)\n- Historische/veraltete Fakten (Entwicklungsprotokoll)\n- Alle beteiligten Entitäten"
    },
    {
        "id": "backend/app/services/report_agent.py:615:33:STRING",
        "kind": "llm_prompt",
        "translation": "\\\nDu bist ein Experte für \"Zukunftsprognose-Berichte\" und verfasst gerade ein Kapitel eines Berichts.\n\nBerichtstitel: {report_title}\nBerichtszusammenfassung: {report_summary}\nPrognoseszenario (Simulationsanforderung): {simulation_requirement}\n\nAktuell zu verfassendes Kapitel: {section_title}\n\n═══════════════════════════════════════════════════════════════\n【Kernidee】\n═══════════════════════════════════════════════════════════════\n\nDie simulierte Welt ist eine Vorschau auf die Zukunft. Wir haben bestimmte Bedingungen (Simulationsanforderungen) eingespeist.\nDas Verhalten und die Interaktionen der Agents in der Simulation sind Vorhersagen über zukünftiges menschliches Verhalten.\n\nDeine Aufgabe ist:\n- Aufzeigen, was unter den gesetzten Bedingungen in der Zukunft passiert\n- Vorhersagen, wie verschiedene Personengruppen (Agents) reagieren und handeln\n- Bemerkenswerte zukünftige Trends, Risiken und Chancen entdecken\n\n❌ Schreibe keine Analyse des aktuellen Zustands der realen Welt\n✅ Fokussiere dich auf \"Wie wird die Zukunft\" — die Simulationsergebnisse SIND die vorhergesagte Zukunft\n\n═══════════════════════════════════════════════════════════════\n【Wichtigste Regeln - Müssen befolgt werden】\n═══════════════════════════════════════════════════════════════\n\n1. 【Tools aufrufen um die simulierte Welt zu beobachten】\n   - Du beobachtest die Zukunftsvorschau aus der \"Gottesperspektive\"\n   - Alle Inhalte müssen aus Ereignissen und Agent-Äußerungen der simulierten Welt stammen\n   - Es ist verboten, dein eigenes Wissen für Berichtsinhalte zu verwenden\n   - Pro Kapitel mindestens 3 Tool-Aufrufe (max. 5) um die simulierte Welt zu beobachten — sie repräsentiert die Zukunft\n\n2. 【Originalaussagen der Agents zitieren】\n   - Äußerungen und Verhalten der Agents sind Vorhersagen über zukünftiges Gruppenverhalten\n   - Im Bericht Zitatformat verwenden um diese Vorhersagen darzustellen, z.B.:\n     > \"Eine bestimmte Personengruppe würde sagen: Originalinhalt...\"\n   - Diese Zitate sind der Kernbeweis der Simulationsvorhersage\n\n3. 【Sprachkonsistenz - Zitierte Inhalte müssen in Berichtssprache übersetzt werden】\n   - Von Tools zurückgegebene Inhalte können in einer anderen Sprache als der Berichtssprache sein\n   - Der Bericht muss durchgehend in der vom Benutzer festgelegten Sprache verfasst sein\n   - Wenn du Tool-Rückgaben in anderer Sprache zitierst, müssen diese vor dem Einfügen übersetzt werden\n   - Bei der Übersetzung die ursprüngliche Bedeutung beibehalten, natürlich formulieren\n   - Diese Regel gilt sowohl für Fließtext als auch für Zitatblöcke (> Format)\n\n4. 【Vorhersageergebnisse treu wiedergeben】\n   - Berichtsinhalte müssen die Simulationsergebnisse der simulierten Welt widerspiegeln\n   - Keine Informationen hinzufügen, die nicht in der Simulation existieren\n   - Bei unzureichenden Informationen dies ehrlich angeben\n\n═══════════════════════════════════════════════════════════════\n【⚠️ Formatvorgaben - Äußerst wichtig!】\n═══════════════════════════════════════════════════════════════\n\n【Ein Kapitel = Kleinste Inhaltseinheit】\n- Jedes Kapitel ist die kleinste Segmentierungseinheit des Berichts\n- ❌ Keine Markdown-Überschriften innerhalb eines Kapitels (#, ##, ###, #### usw.)\n- ❌ Keine Kapitelhauptüberschrift am Anfang\n- ✅ Kapitelüberschrift wird automatisch vom System hinzugefügt, du schreibst nur reinen Fließtext\n- ✅ **Fett**, Absatztrennung, Zitate, Listen zur Strukturierung verwenden, aber keine Überschriften\n\n【Richtiges Beispiel】\n```\nDieses Kapitel analysiert die Meinungsverbreitung des Ereignisses. Durch eingehende Analyse der Simulationsdaten stellen wir fest...\n\n**Erste Zündungsphase**\n\nWeibo als erster Schauplatz der Meinungsbildung übernahm die Kernfunktion der Erstveröffentlichung:\n\n> \"Weibo trug 68% des Erstveröffentlichungsvolumens bei...\"\n\n**Emotionsverstärkungsphase**\n\nDouyin verstärkte die Ereigniswirkung weiter:\n\n- Starke visuelle Wirkung\n- Hohe emotionale Resonanz\n```\n\n【Falsches Beispiel】\n```\n## Executive Summary          ← Falsch! Keine Überschriften\n### 1. Erste Phase     ← Falsch! Kein ### für Unterabschnitte\n#### 1.1 Detailanalyse   ← Falsch! Kein #### für Unterteilung\n\nDieses Kapitel analysiert...\n```\n\n═══════════════════════════════════════════════════════════════\n【Verfügbare Retrieval-Tools】(3-5 Aufrufe pro Kapitel)\n═══════════════════════════════════════════════════════════════\n\n{tools_description}\n\n【Tool-Nutzungsempfehlung - Bitte verschiedene Tools mischen, nicht nur eines verwenden】\n- insight_forge: Tiefgehende Erkenntnisanalyse, zerlegt Fragen automatisch und recherchiert Fakten und Beziehungen multidimensional\n- panorama_search: Weitwinkel-Panoramasuche, Gesamtbild des Ereignisses, Zeitachse und Entwicklung verstehen\n- quick_search: Schnelle Überprüfung eines konkreten Informationspunkts\n- interview_agents: Simulations-Agents befragen, Perspektiven und echte Reaktionen verschiedener Rollen in erster Person erhalten\n\n═══════════════════════════════════════════════════════════════\n【Arbeitsablauf】\n═══════════════════════════════════════════════════════════════\n\nPro Antwort kannst du nur EINE der folgenden zwei Optionen wählen (nicht beide gleichzeitig):\n\nOption A - Tool aufrufen:\nGib deine Überlegungen aus, dann rufe ein Tool im folgenden Format auf:\n<tool_call>\n{{\"name\": \"Toolname\", \"parameters\": {{\"Parametername\": \"Parameterwert\"}}}}\n</tool_call>\nDas System führt das Tool aus und gibt das Ergebnis zurück. Du brauchst das Tool-Ergebnis nicht selbst zu schreiben.\n\nOption B - Endgültigen Inhalt ausgeben:\nWenn du durch Tools genügend Informationen gesammelt hast, beginne mit \"Final Answer:\" und gib den Kapitelinhalt aus.\n\n⚠️ Strikt verboten:\n- Tool-Aufruf und Final Answer in einer Antwort kombinieren\n- Tool-Ergebnisse (Observations) selbst erfinden — alle Tool-Ergebnisse werden vom System injiziert\n- Mehr als ein Tool pro Antwort aufrufen\n\n═══════════════════════════════════════════════════════════════\n【Kapitelinhalt-Anforderungen】\n═══════════════════════════════════════════════════════════════\n\n1. Inhalt muss auf durch Tools abgerufenen Simulationsdaten basieren\n2. Reichlich Originaltext zitieren um Simulationseffekte zu zeigen\n3. Markdown-Format verwenden (aber KEINE Überschriften):\n   - **Fetten Text** für Hervorhebungen verwenden (statt Unterüberschriften)\n   - Listen (- oder 1.2.3.) für Aufzählungen verwenden\n   - Leerzeilen zur Absatztrennung\n   - ❌ Keine #, ##, ###, #### oder andere Überschriftensyntax\n4. 【Zitatformat - Muss eigenständiger Absatz sein】\n   Zitate müssen als eigener Absatz stehen, mit je einer Leerzeile davor und danach, nicht in Absätze eingebettet:\n\n   ✅ Richtiges Format:\n   ```\n   Die Reaktion der Hochschule wurde als substanzlos bewertet.\n\n   > \"Die Reaktionsweise der Hochschule wirkt in der schnelllebigen Social-Media-Umgebung starr und träge.\"\n\n   Diese Bewertung spiegelt die allgemeine Unzufriedenheit der Öffentlichkeit wider.\n   ```\n\n   ❌ Falsches Format:\n   ```\n   Die Reaktion der Hochschule wurde als substanzlos bewertet. > \"Die Reaktionsweise...\" Diese Bewertung spiegelt...\n   ```\n5. Logische Kohärenz mit anderen Kapiteln wahren\n6. 【Wiederholungen vermeiden】Die unten aufgeführten fertigen Kapitel sorgfältig lesen, keine gleichen Informationen wiederholen\n7. 【Nochmals betont】Keine Überschriften! **Fett** statt Unterüberschriften verwenden"
    },
    {
        "id": "backend/app/services/report_agent.py:866:4:STRING",
        "kind": "docstring",
        "translation": "\n    Report Agent - Simulations-Berichtgenerierungs-Agent\n\n    Verwendet den ReACT-Modus (Reasoning + Acting):\n    1. Planungsphase: Simulationsanforderungen analysieren, Berichts-Gliederung planen\n    2. Generierungsphase: Kapitelweise Inhalt generieren, pro Kapitel mehrfach Tools aufrufen\n    3. Reflexionsphase: Vollständigkeit und Korrektheit des Inhalts prüfen\n    "
    },
    {
        "id": "backend/app/services/report_agent.py:892:8:STRING",
        "kind": "docstring",
        "translation": "\n        Report Agent initialisieren\n        \n        Args:\n            graph_id: Graph-ID\n            simulation_id: Simulations-ID\n            simulation_requirement: Beschreibung der Simulationsanforderung\n            llm_client: LLM-Client (optional)\n            zep_tools: Zep-Tool-Service (optional)\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:957:8:STRING",
        "kind": "docstring",
        "translation": "\n        Tool-Aufruf ausführen\n        \n        Args:\n            tool_name: Tool-Name\n            parameters: Tool-Parameter\n            report_context: Berichtskontext (für InsightForge)\n            \n        Returns:\n            Tool-Ausführungsergebnis (Textformat)\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:1068:8:STRING",
        "kind": "docstring",
        "translation": "\n        Tool-Aufrufe aus LLM-Antwort parsen\n\n        Unterstützte Formate (nach Priorität):\n        1. <tool_call>{\"name\": \"tool_name\", \"parameters\": {...}}</tool_call>\n        2. Rohes JSON (Antwort insgesamt oder einzelne Zeile ist ein Tool-Aufruf-JSON)\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:1141:8:STRING",
        "kind": "docstring",
        "translation": "\n        Berichts-Gliederung planen\n        \n        Verwendet LLM zur Analyse der Simulationsanforderungen und plant die Inhaltsverzeichnisstruktur\n        \n        Args:\n            progress_callback: Fortschritts-Callback-Funktion\n            \n        Returns:\n            ReportOutline: Berichts-Gliederung\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:1229:8:STRING",
        "kind": "docstring",
        "translation": "\n        Einzelnes Kapitel im ReACT-Modus generieren\n        \n        ReACT-Zyklus:\n        1. Thought (Denken) - Analysieren welche Informationen benötigt werden\n        2. Action (Handeln) - Tools aufrufen um Informationen zu erhalten\n        3. Observation (Beobachten) - Tool-Ergebnisse analysieren\n        4. Wiederholen bis genug Informationen vorhanden oder Maximum erreicht\n        5. Final Answer (Endantwort) - Kapitelinhalt generieren\n        \n        Args:\n            section: Zu generierendes Kapitel\n            outline: Vollständige Gliederung\n            previous_sections: Inhalt vorheriger Kapitel (für Kohärenz)\n            progress_callback: Fortschritts-Callback\n            section_index: Kapitelindex (für Protokollierung)\n            \n        Returns:\n            Kapitelinhalt (Markdown-Format)\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:1537:8:STRING",
        "kind": "docstring",
        "translation": "\n        Vollständigen Bericht generieren (kapitelweise Echtzeit-Ausgabe)\n        \n        Jedes fertige Kapitel wird sofort gespeichert, ohne auf den gesamten Bericht zu warten.\n        Dateistruktur:\n        reports/{report_id}/\n            meta.json       - Bericht-Metainformationen\n            outline.json    - Berichts-Gliederung\n            progress.json   - Generierungsfortschritt\n            section_01.md   - Kapitel 1\n            section_02.md   - Kapitel 2\n            ...\n            full_report.md  - Vollständiger Bericht\n        \n        Args:\n            progress_callback: Fortschritts-Callback-Funktion (stage, progress, message)\n            report_id: Bericht-ID (optional, wird sonst automatisch generiert)\n            \n        Returns:\n            Report: Vollständiger Bericht\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:1771:8:STRING",
        "kind": "docstring",
        "translation": "\n        Mit dem Report Agent kommunizieren\n        \n        Im Gespräch kann der Agent eigenständig Retrieval-Tools aufrufen um Fragen zu beantworten\n        \n        Args:\n            message: Benutzernachricht\n            chat_history: Gesprächsverlauf\n            \n        Returns:\n            {\n                \"response\": \"Agent-Antwort\",\n                \"tool_calls\": [Liste aufgerufener Tools],\n                \"sources\": [Informationsquellen]\n            }\n        "
    },
    {
        "id": "backend/app/services/report_agent.py:1885:4:STRING",
        "kind": "docstring",
        "translation": "\n    Bericht-Manager\n    \n    Zuständig für persistente Speicherung und Abruf von Berichten\n    \n    Dateistruktur (kapitelweise Ausgabe):\n    reports/\n      {report_id}/\n        meta.json          - Bericht-Metainformationen und Status\n        outline.json       - Berichts-Gliederung\n        progress.json      - Generierungsfortschritt\n        section_01.md      - Kapitel 1\n        section_02.md      - Kapitel 2\n        ...\n        full_report.md     - Vollständiger Bericht\n    "
    },
    {
        "id": "backend/app/services/simulation_config_generator.py:565:2:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": "\n    \"total_simulation_hours\": 72,\n    \"minutes_per_round\": 60,\n    \"agents_per_hour_min\": 5,\n    \"agents_per_hour_max\": 50,\n    \"peak_hours\": [19, 20, 21, 22],\n    \"off_peak_hours\": [0, 1, 2, 3, 4, 5],\n    \"morning_hours\": [6, 7, 8],\n    \"work_hours\": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],\n    \"reasoning\": \"Zeitkonfigurationserklärung für dieses Ereignis\"\n}"
    },
    {
        "id": "backend/app/services/simulation_config_generator.py:629:29:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": "agents_per_hour_min >= max, wurde korrigiert auf "
    },
    {
        "id": "backend/app/services/simulation_config_generator.py:699:64:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": ",\n        ...\n    ],\n    \"reasoning\": \"<Kurze Erklärung>\"\n}"
    },
    {
        "id": "backend/app/services/simulation_config_generator.py:794:33:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": "Typ nicht gefunden: '"
    },
    {
        "id": "backend/app/services/simulation_config_generator.py:833:21:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": "Basierend auf folgenden Informationen, generiere Social-Media-Aktivitätskonfigurationen für jede Entität.\n\nSimulationsanforderung: "
    },
    {
        "id": "backend/app/services/simulation_config_generator.py:839:55:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": "\n```\n\n## Aufgabe\nFür jede Entität Aktivitätskonfiguration generieren, beachte:\n- **Zeiten passend zur Zielgruppe**: Nachfolgendes als Referenz (UTC+8), bitte an das Simulationsszenario anpassen\n- **Offizielle Institutionen** (University/GovernmentAgency): Niedrige Aktivität (0.1-0.3), Geschäftszeiten (9-17) aktiv, langsame Reaktion (60-240 Minuten), hoher Einfluss (2.5-3.0)\n- **Medien** (MediaOutlet): Mittlere Aktivität (0.4-0.6), ganztags aktiv (8-23), schnelle Reaktion (5-30 Minuten), hoher Einfluss (2.0-2.5)\n- **Privatpersonen** (Student/Person/Alumni): Hohe Aktivität (0.6-0.9), hauptsächlich abends aktiv (18-23), schnelle Reaktion (1-15 Minuten), niedriger Einfluss (0.8-1.2)\n- **Öffentliche Personen/Experten**: Mittlere Aktivität (0.4-0.6), mittlerer bis hoher Einfluss (1.5-2.0)\n\nJSON-Format zurückgeben (kein Markdown):\n{"
    },
    {
        "id": "backend/app/services/simulation_config_generator.py:853:10:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": "\n            \"agent_id\": <muss mit Eingabe übereinstimmen>,\n            \"activity_level\": <0.0-1.0>,\n            \"posts_per_hour\": <Posting-Frequenz>,\n            \"comments_per_hour\": <Kommentar-Frequenz>,\n            \"active_hours\": [<Liste aktiver Stunden, Tagesrhythmus berücksichtigen>],\n            \"response_delay_min\": <Min. Antwortverzögerung in Minuten>,\n            \"response_delay_max\": <Max. Antwortverzögerung in Minuten>,\n            \"sentiment_bias\": <-1.0 bis 1.0>,\n            \"stance\": \"<supportive/opposing/neutral/observer>\",\n            \"influence_weight\": <Einflussgewichtung>\n        }"
    },
    {
        "id": "backend/app/services/zep_entity_reader.py:410:27:FSTRING_MIDDLE",
        "kind": "fstring_text",
        "translation": "Entität abrufen "
    },
    {
        "id": "backend/app/utils/llm_client.py:66:8:COMMENT",
        "kind": "comment",
        "translation": "Einige Modelle (z.B. MiniMax M2.5) enthalten <think>-Denkinhalt im content, der entfernt werden muss"
    },
]

# Read segments to get source_text for each translation
segments = {}
with open('scripts/i18n/output/segments.jsonl') as f:
    for line in f:
        seg = json.loads(line)
        segments[seg['id']] = seg

# Write translations to translations.jsonl
with open('scripts/i18n/output/translations.jsonl', 'a') as f:
    for t in translations:
        seg = segments[t['id']]
        entry = {
            "id": t['id'],
            "kind": t['kind'],
            "source_text": seg['source_text'],
            "translation": t['translation'],
            "batch_id": "manual"
        }
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

print(f"Appended {len(translations)} manual translations to translations.jsonl")

# Verify total
translated_ids = set()
with open('scripts/i18n/output/translations.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        translated_ids.add(entry['id'])
print(f"Total translations now: {len(translated_ids)}")
