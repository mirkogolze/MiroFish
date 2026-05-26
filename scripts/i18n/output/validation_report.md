# Translation Validation Report

## Summary

| Status | Count | % |
|--------|-------|---|
| auto-accepted | 1520 | 86.0% |
| spot-check | 186 | 10.5% |
| manual-review | 25 | 1.4% |
| rejected | 37 | 2.1% |
| **Total** | **1768** | **100%** |

## By Kind

| Kind | Auto | Spot | Manual | Rejected |
|------|------|------|--------|----------|
| comment | 805 | 112 | 2 | 0 |
| docstring | 181 | 1 | 4 | 27 |
| error_message | 3 | 0 | 0 | 0 |
| fstring_text | 298 | 21 | 14 | 0 |
| llm_prompt | 2 | 0 | 1 | 10 |
| string_constant | 231 | 52 | 4 | 0 |

## Flagged Items (248 total, showing first 100)

| Score | Kind | ID | Flags | Source (first 60) | Translation (first 60) |
|-------|------|----|----|--------|-------------|
| 60 | fstring_text | `d/app/api/graph.py:213:46:FSTRING_MIDDLE` | IDENTICAL_TO_SOURCE |  字符 |  字符 |
| 60 | docstring | `p/services/report_agent.py:476:26:STRING` | CJK_RESIDUE: 强大的检索函数专为深 | \ 【深度洞察检索 - 强大的检索工具】 这是我们强大的检索函数，专为深度分析设计。它会： 1. 自动将你的问题分解为多 | \ 【Tiefeinsichten-Suche - Eine mächtige Suchfunktion】 Dies i |
| 70 | comment | `services/report_agent.py:2387:20:COMMENT` | MARKDOWN_ARTIFACTS | ### 及以下级别的标题转换为粗体文本 | ### und niedriger Überschriften in Fettdrucktext konvertiere |
| 70 | comment | `ces/simulation_manager.py:438:12:COMMENT` | EXPLANATION_TEXT: 'Hinweis:' | 注意：运行脚本保留在 backend/scripts/ 目录，不再复制到模拟目录 | Hinweis: Die Ausführungs-Scripts bleiben im backend/scripts/ |
| 70 | docstring | `backend/app/api/graph.py:262:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "project_id": "proj_xxxx",\n          |      接口2：根据project_id构建图谱          请求（JSON）：         {       |      Schnittstelle 2: Graphen basierend auf project_id erste |
| 70 | docstring | `backend/app/api/report.py:27:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "simulation_id": "sim_xxxx",\n        |      生成模拟分析报告（异步任务）          这是一个耗时操作，接口会立即返回task_id，     使用 |      Simulationsbericht generieren (asynchron)          Dies |
| 70 | docstring | `backend/app/api/report.py:205:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "task_id": "task_xxxx",         // 可选，gen |      查询报告生成任务进度          请求（JSON）：         {             "ta |      Fortschritt der Berichtserstellungsaufgabe abfragen     |
| 70 | docstring | `p/services/report_agent.py:1959:8:STRING` | MISSING_PLACEHOLDERS: {'{\n                "logs": [日志行列表],\n                "to |          获取控制台日志内容                  这是报告生成过程中的控制台输出日志（INFO、W |          Holt den Inhalt der Konsolenprotokolle.             |
| 70 | docstring | `p/services/report_agent.py:2020:8:STRING` | MISSING_PLACEHOLDERS: {'{\n                "logs": [日志条目列表],\n                "t |          获取 Agent 日志内容                  Args:             re |          Holt den Inhalt der Agent-Protokolle.               |
| 70 | docstring | `/services/simulation_ipc.py:230:8:STRING` | MISSING_PLACEHOLDERS: {'{"agent_id": int, "prompt": str, "platform": str(可选)}'}; |          发送批量采访命令                  Args:             intervi |          Send batch interview commands                  Args |
| 70 | docstring | `vices/simulation_runner.py:1104:8:STRING` | EXPLANATION_TEXT: 'Hinweis:' |          清理模拟的运行日志（用于强制重新开始模拟）                  会删除以下文件：     |          Bereinige die Laufzeit-Logs der Simulation (für ein |
| 70 | docstring | `vices/simulation_runner.py:1499:8:STRING` | MISSING_PLACEHOLDERS: {'{"agent_id": int, "prompt": str, "platform": str(可选)}'}; |          批量采访多个Agent          Args:             simulation_i |          Führe ein Batch-Interview mit mehreren Agents       |
| 70 | docstring | `app/services/zep_tools.py:1580:24:STRING` | MISSING_PLACEHOLDERS: {'{\n    "selected_indices": [选中Agent的索引列表],\n    "reasoni | 你是一个专业的采访策划专家。你的任务是根据采访需求，从模拟Agent列表中选择最适合采访的对象。  选择标准： 1. A | Sie sind ein Experte für Interviewplanung. Ihre Aufgabe ist  |
| 70 | docstring | `backend/app/utils/retry.py:156:8:STRING` | MARKDOWN_ARTIFACTS |          执行函数调用并在失败时重试                  Args:             fu |  Funktionsaufrufe ausführen und bei Fehlern wiederholen  Arg |
| 70 | fstring_text | `ology_generator.py:248:22:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS | ## 模拟需求   | ## Simulationsanforderung   |
| 70 | fstring_text | `ology_generator.py:250:24:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS |   ## 文档内容   |   ## Dokumentinhalt   |
| 70 | fstring_text | `ology_generator.py:258:27:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS |  ## 额外说明   |  ## Zusätzliche Hinweise   |
| 70 | fstring_text | `onfig_generator.py:394:14:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS | ## 模拟需求\n | ## Simulationsanforderung\n |
| 70 | fstring_text | `vices/zep_tools.py:174:14:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS | ## 未来预测深度分析 | ## Zukunftsprognose-Tiefenanalyse |
| 70 | fstring_text | `vices/zep_tools.py:253:14:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS | ## 广度搜索结果（未来全景视图） | ## Breitensuchergebnisse (Zukunftsgesamtansicht) |
| 70 | fstring_text | `vices/zep_tools.py:379:14:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS | **采访主题:**  | **Interviewthema:** |
| 70 | fstring_text | `vices/zep_tools.py:380:14:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS | **采访人数:**  | **Anzahl der Interviewteile:** |
| 70 | llm_prompt | `p/services/report_agent.py:829:30:STRING` | MISSING_PLACEHOLDERS: {'{"参数名": "参数值"}'}; EXTRA_PLACEHOLDERS: {'{"Parametername" | \ 你是一个简洁高效的模拟预测助手。  【背景】 预测条件: {simulation_requirement}  【已生 | \nDu bist ein präziser und effizienter Vorhersagemodell-Assi |
| 70 | llm_prompt | `app/services/zep_tools.py:1104:24:STRING` | MISSING_PLACEHOLDERS: {'{"sub_queries": ["子问题1", "子问题2", ...]}'}; EXTRA_PLACEHOL | 你是一个专业的问题分析专家。你的任务是将一个复杂问题分解为多个可以在模拟世界中独立观察的子问题。  要求： 1. 每个子 | Du bist ein Experte für die Analyse von Problemen. Deine Auf |
| 70 | llm_prompt | `app/services/zep_tools.py:1644:24:STRING` | MISSING_PLACEHOLDERS: {'{"questions": ["问题1", "问题2", ...]}'}; EXTRA_PLACEHOLDERS | 你是一个专业的记者/采访者。根据采访需求，生成3-5个深度采访问题。  问题要求： 1. 开放性问题，鼓励详细回答 2. | Du bist ein professioneller Journalist/Interviewer. Erstelle |
| 70 | string_constant | `ices/ontology_generator.py:420:12:STRING` | MARKDOWN_ARTIFACTS | # ============== 实体类型定义 ============== | # ============== Entitätstypen-Definition ============== |
| 70 | string_constant | `ices/ontology_generator.py:447:26:STRING` | MARKDOWN_ARTIFACTS | # ============== 关系类型定义 ============== | # ============== Relationentypen-Definition ============== |
| 70 | string_constant | `ices/ontology_generator.py:476:26:STRING` | MARKDOWN_ARTIFACTS | # ============== 类型配置 ============== | # ============== Typkonfiguration ============== |
| 70 | string_constant | `/app/services/zep_tools.py:378:12:STRING` | MARKDOWN_ARTIFACTS | ## 深度采访报告 | ## Tiefeninterviewbericht |
| 70 | docstring | `backend/app/api/report.py:612:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                        "filename": "section_01.md",\ |      获取已生成的章节列表（分章节输出）          前端可以轮询此接口获取已生成的章节内容，无需等待整个报告 |      Ruft eine Liste der bereits generierten Kapitel ab (Kap |
| 70 | docstring | `backend/app/api/report.py:709:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "simulation_id": "sim_xxxx",\n        |      检查模拟是否有报告，以及报告状态          用于前端判断是否解锁Interview功能         |  	Überprüfen, ob eine Simulation einen Bericht hat und den S |
| 70 | docstring | `ckend/app/api/simulation.py:241:4:STRING` | EXPLANATION_TEXT: 'Hinweis:' |      检查模拟是否已经准备完成          检查条件：     1. state.json 存在且 statu |  	Überprüfen, ob die Simulation bereits fertig vorbereitet i |
| 70 | docstring | `ckend/app/api/simulation.py:644:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "task_id": "task_xxxx",          // 可选，pr |      查询准备任务进度          支持两种查询方式：     1. 通过task_id查询正在进行的任务进度 |  	Abfrage des Vorbereitungsauftragsstatus 	 	Zwei Abfragemet |
| 70 | docstring | `ckend/app/api/simulation.py:878:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                    "simulation_id": "sim_xxxx",\n    |      获取历史模拟列表（带项目详情）          用于首页历史项目展示，返回包含项目名称、描述等丰富信息的模拟 |      Holt die Liste der historischen Simulationsprojekte (mi |
| 70 | docstring | `kend/app/api/simulation.py:1030:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "simulation_id": "sim_xxxx",\n        |      实时获取模拟的Agent Profile（用于在生成过程中实时查看进度）          与 /profil |  	Echtzeit-Abruf des Agenten-Profiles der Simulation (zum Ec |
| 70 | docstring | `kend/app/api/simulation.py:1453:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "simulation_id": "sim_xxxx",\n        |      开始运行模拟      请求（JSON）：         {             "simulation |  	Starte die Simulation ausführen.  	Anfrage (JSON): 	{ 		"s |
| 70 | docstring | `kend/app/api/simulation.py:1646:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "simulation_id": "sim_xxxx"  // 必填，模拟ID\n |      停止模拟          请求（JSON）：         {             "simulati |  	Stoppe die Simulation 	 	Anfrage (JSON): 		{ 			"simulatio |
| 70 | docstring | `kend/app/api/simulation.py:1866:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "count": 100,\n                "actio |      获取模拟中的Agent动作历史          Query参数：         limit: 返回数量（默 |  	Abrufen der Aktionshistorie des Agents in der Simulation 	 |
| 70 | docstring | `kend/app/api/simulation.py:2651:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "simulation_id": "sim_xxxx",  // 必填，模拟ID\ |      关闭模拟环境          向模拟发送关闭环境命令，使其优雅退出等待命令模式。          注意：这 |  	Schliët das Simulationsumgebung 	 	Sendet dem Simulator d |
| 70 | fstring_text | `onfig_generator.py:545:19:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS |   ## 任务 请生成时间配置JSON。  ### 基本原则（仅供参考，需根据具体事件和参与群体灵活调整）： - 请根据 |   ## Aufgabe Bitte generieren Sie die Zeitkonfiguration JSON |
| 70 | fstring_text | `onfig_generator.py:680:19:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS |   ## 可用实体类型及示例  |   ## Verfügbare Entitätstypen und Beispiele  |
| 70 | fstring_text | `onfig_generator.py:683:11:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS |   ## 任务 请生成事件配置JSON： - 提取热点话题关键词 - 描述舆论发展方向 - 设计初始帖子内容，**每个帖 |   ## Aufgabe Bitte generieren Sie die Ereigniskonfiguration  |
| 70 | fstring_text | `onfig_generator.py:835:30:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS |   ## 实体列表 ```json  |   ## Liste der Entitäten ```json  |
| 70 | llm_prompt | `ckend/app/api/simulation.py:361:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "simulation_id": "sim_xxxx",              |      准备模拟环境（异步任务，LLM智能生成所有参数）          这是一个耗时操作，接口会立即返回task_ |  	Vorbereitung des Simulationsumfelds (asynchrone Aufgabe, L |
| 70 | llm_prompt | `kend/app/api/simulation.py:2144:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                    "agent_id": 0,\n                  |      采访单个Agent      注意：此功能需要模拟环境处于运行状态（完成模拟循环后进入等待命令模式）      |      Interview eines einzelnen Agents      Hinweis: Diese Fu |
| 70 | llm_prompt | `kend/app/api/simulation.py:2273:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                    "agent_id": 1,\n                  |      批量采访多个Agent      注意：此功能需要模拟环境处于运行状态      请求（JSON）：      |      Mehrere Agenten in einem Batch interviewen      Hinweis |
| 70 | llm_prompt | `kend/app/api/simulation.py:2411:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "simulation_id": "sim_xxxx",            / |      全局采访 - 使用相同问题采访所有Agent      注意：此功能需要模拟环境处于运行状态      请求（ |      Globale Interviews - Alle Agenten werden mit der gleich |
| 70 | llm_prompt | `ices/ontology_generator.py:264:19:STRING` | MARKDOWN_ARTIFACTS |  请根据以上内容，设计适合社会舆论模拟的实体类型和关系类型。  **必须遵守的规则**： 1. 必须正好输出10个实体类 |  Basierend auf den obigen Informationen sollst du die passen |
| 70 | llm_prompt | `p/services/report_agent.py:552:21:STRING` | MISSING_PLACEHOLDERS: {'{\n            "title": "章节标题",\n            "descriptio | \ 你是一个「未来预测报告」的撰写专家，拥有对模拟世界的「上帝视角」——你可以洞察模拟中每一位Agent的行为、言论和互 | \ Sie sind ein Experte für die Erstellung von "Zukunftsvorhe |
| 70 | docstring | `backend/app/api/report.py:474:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "response": "Agent回复...",\n           |      与Report Agent对话          Report Agent可以在对话中自主调用检索工具来回答问 |      Mit dem Report Agent kommunizieren          Der Report  |
| 70 | docstring | `backend/app/api/report.py:571:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "status": "generating",\n             |      获取报告生成进度（实时）          返回：         {             "succes |      Berichterstellungs-Fortschritt abrufen (Echtzeit)       |
| 70 | docstring | `backend/app/api/report.py:663:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "filename": "section_01.md",\n        |      获取单个章节内容          返回：         {             "success":  |      Einzelnes Kapitel abrufen          Rückgabe:         {  |
| 70 | docstring | `backend/app/api/report.py:855:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "logs": [\n                    "[19:4 |      获取 Report Agent 的控制台输出日志          实时获取报告生成过程中的控制台输出（INF |      Konsolenausgabe-Protokoll des Report Agent abrufen      |
| 70 | docstring | `backend/app/api/report.py:937:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "graph_id": "mirofish_xxxx",\n            |      图谱搜索工具接口（供调试使用）          请求（JSON）：         {            |      Graph-Such-Tool-Schnittstelle (für Debugging)           |
| 70 | docstring | `ckend/app/api/simulation.py:167:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "project_id": "proj_xxxx",      // 必填\n   |      创建新的模拟          注意：max_rounds等参数由LLM智能生成，无需手动设置         |      Neue Simulation erstellen          Hinweis: Parameter w |
| 70 | docstring | `kend/app/api/simulation.py:1379:4:STRING` | MISSING_PLACEHOLDERS: {'{\n            "graph_id": "mirofish_xxxx",     // 必填\n  |      直接从图谱生成OASIS Agent Profile（不创建模拟）          请求（JSON）：    |      OASIS Agent Profile direkt aus dem Graphen generieren ( |
| 70 | docstring | `kend/app/api/simulation.py:2514:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                        "agent_id": 0,\n              |      获取Interview历史记录      从模拟数据库中读取所有Interview记录      请求（JSO |      Interview-Verlauf abrufen      Liest alle Interview-Ein |
| 70 | docstring | `kend/app/api/simulation.py:2586:4:STRING` | MISSING_PLACEHOLDERS: {'{\n                "simulation_id": "sim_xxxx",\n        |      获取模拟环境状态      检查模拟环境是否存活（可以接收Interview命令）      请求（JSON） |      Simulationsumgebungsstatus abrufen      Prüft ob die Si |
| 70 | llm_prompt | `vices/ontology_generator.py:30:25:STRING` | MISSING_PLACEHOLDERS: {'{\n                    "name": "属性名（英文，snake_case）",\n   | 你是一个专业的知识图谱本体设计专家。你的任务是分析给定的文本内容和模拟需求，设计适合**社交媒体舆论模拟**的实体类型和 | Du bist ein professioneller Experte für Wissensgraph-Ontolog |
| 70 | llm_prompt | `p/services/report_agent.py:615:33:STRING` | MISSING_PLACEHOLDERS: {'{"参数名": "参数值"}'}; EXTRA_PLACEHOLDERS: {'{"Parametername" | \ 你是一个「未来预测报告」的撰写专家，正在撰写报告的一个章节。  报告标题: {report_title} 报告摘要: | \ Du bist ein Experte für "Zukunftsprognose-Berichte" und ve |
| 70 | docstring | `p/services/report_agent.py:1771:8:STRING` | MISSING_PLACEHOLDERS: {'{\n                "response": "Agent回复",\n              |          与Report Agent对话                  在对话中Agent可以自主调用检索工 |          Mit dem Report Agent kommunizieren                  |
| 70 | fstring_text | `onfig_generator.py:839:55:FSTRING_MIDDLE` | MARKDOWN_ARTIFACTS |  ```  ## 任务 为每个实体生成活动配置，注意： - **时间符合目标用户群体作息**：以下为参考（东八区），请根 |  ```  ## Aufgabe Für jede Entität Aktivitätskonfiguration ge |
| 85 | comment | `backend/app/__init__.py:45:4:COMMENT` | TOO_LONG: ratio=5.11 | 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程） | Registriere Simulationsprozess-Cleanup-Funktion (stelle sich |
| 85 | comment | `backend/app/__init__.py:65:4:COMMENT` | TOO_LONG: ratio=5.25 | 注册蓝图 | Registriere Blaupause |
| 85 | comment | `backend/app/api/graph.py:344:8:COMMENT` | TOO_LONG: ratio=5.67 | 更新项目配置 | Aktualisiere Projekt-Konfiguration |
| 85 | comment | `backend/app/api/report.py:72:8:COMMENT` | TOO_LONG: ratio=5.25 | 检查是否已有报告 | Prüfe, ob bereits ein Report vorhanden ist |
| 85 | comment | `ckend/app/api/simulation.py:40:4:COMMENT` | TOO_LONG: ratio=5.62 | 避免重复添加前缀 | Verhindere doppelte Hinzufügung des Vorsatzes |
| 85 | comment | `kend/app/api/simulation.py:300:8:COMMENT` | TOO_LONG: ratio=6.50 | 详细日志 | Detailierte Protokolldatei |
| 85 | comment | `kend/app/api/simulation.py:424:8:COMMENT` | TOO_LONG: ratio=6.10 | 检查是否强制重新生成 | Überprüfe, ob eine erzwungene NeuGenerierung erforderlich is |
| 85 | comment | `kend/app/api/simulation.py:428:8:COMMENT` | TOO_LONG: ratio=5.50 | 检查是否已经准备完成（避免重复生成） | Überprüfe, ob die Vorbereitung bereits abgeschlossen wurde ( |
| 85 | comment | `end/app/api/simulation.py:480:41:COMMENT` | TOO_LONG: ratio=6.18 | 不获取边信息，加快速度 | Keine Kanteninformationen abrufen, um die Geschwindigkeit zu |
| 85 | comment | `end/app/api/simulation.py:488:12:COMMENT` | TOO_LONG: ratio=5.21 | 失败不影响后续流程，后台任务会重新获取 | Fehlschläge beeinflussen den nachfolgenden Prozess nicht, de |
| 85 | comment | `end/app/api/simulation.py:518:16:COMMENT` | TOO_LONG: ratio=5.18 | 准备模拟（带进度回调） | Vorbereitung der Simulation (mit Fortschrittsrückmeldung) |
| 85 | comment | `end/app/api/simulation.py:519:16:COMMENT` | TOO_LONG: ratio=5.25 | 存储阶段进度详情 | Speichere Details des Fortschrittsstadiums |
| 85 | comment | `end/app/api/simulation.py:523:20:COMMENT` | TOO_LONG: ratio=5.20 | 计算总进度 | Berechne Gesamtfortschritt |
| 85 | comment | `end/app/api/simulation.py:534:20:COMMENT` | TOO_LONG: ratio=5.88 | 构建详细进度信息 | Erstelle detaillierte Fortschrittsinformationen |
| 85 | comment | `end/app/api/simulation.py:593:16:COMMENT` | TOO_LONG: ratio=5.25 | 任务完成 | Auftrag abgeschlossen |
| 85 | comment | `end/app/api/simulation.py:603:16:COMMENT` | TOO_LONG: ratio=5.89 | 更新模拟状态为失败 | Aktualisiere den Simulationsstatus auf fehlgeschlagen |
| 85 | comment | `kend/app/api/simulation.py:867:8:COMMENT` | TOO_LONG: ratio=5.60 | 按创建时间倒序排序，返回最新的 | Sortiere nach Erstellungszeit in absteigender Reihenfolge un |
| 85 | comment | `end/app/api/simulation.py:1063:8:COMMENT` | TOO_LONG: ratio=5.83 | 获取模拟目录 | Lese den Simulationsverzeichnispfad |
| 85 | comment | `end/app/api/simulation.py:1220:8:COMMENT` | TOO_LONG: ratio=5.33 | 构建返回数据 | Erstelle das Rückgabedatenobjekt |
| 85 | comment | `nd/app/api/simulation.py:1578:16:COMMENT` | TOO_LONG: ratio=5.29 | 准备工作未完成 | Vorbereitung noch nicht abgeschlossen |
| 85 | comment | `end/app/api/simulation.py:1612:8:COMMENT` | TOO_LONG: ratio=5.67 | 更新模拟状态 | Aktualisiere den Simulationsstatus |
| 85 | comment | `end/app/api/simulation.py:1822:8:COMMENT` | TOO_LONG: ratio=5.43 | 分平台获取动作 | Platform-basierte Abfrage von Aktionen |
| 85 | comment | `end/app/api/simulation.py:1841:8:COMMENT` | TOO_LONG: ratio=5.38 | 获取基础状态信息 | Abfrage der grundlegenden Statusinformation |
| 85 | comment | `nd/app/api/simulation.py:2550:41:COMMENT` | TOO_LONG: ratio=5.15 | 不指定则返回两个平台的历史 | Keine Angabe bedeutet Rückgabe der Geschichte für beide Plat |
| 85 | comment | `ckend/app/models/project.py:47:4:COMMENT` | TOO_LONG: ratio=6.50 | 配置 | Konfiguration |
| 85 | comment | `kend/app/models/project.py:216:8:COMMENT` | TOO_LONG: ratio=6.33 | 按创建时间倒序排序 | Sortiere nach Erstellungszeit in absteigender Reihenfolge |
| 85 | comment | `backend/app/models/task.py:37:57:COMMENT` | TOO_LONG: ratio=6.33 | 详细进度信息 | Detaillierte Fortschrittsinformationen |
| 85 | comment | `services/graph_builder.py:244:12:COMMENT` | TOO_LONG: ratio=6.60 | 动态创建类 | Dynamische Erstellung von Klassen |
| 85 | comment | `/services/graph_builder.py:249:8:COMMENT` | TOO_LONG: ratio=5.43 | 动态创建边类型 | Dynamische Erstellung von Kanten-Typen |
| 85 | comment | `services/graph_builder.py:337:16:COMMENT` | TOO_LONG: ratio=5.17 | 避免请求过快 | Verhindere zu schnelle Anfragen |
| 85 | comment | `ices/ontology_generator.py:280:8:COMMENT` | TOO_LONG: ratio=6.50 | 确保必要字段存在 | Stelle sicher, dass notwendige Felder vorhanden sind |
| 85 | comment | `ices/ontology_generator.py:365:8:COMMENT` | TOO_LONG: ratio=5.10 | 检查是否已有兜底类型 | Überprüfe, ob bereits Fallback-Typen vorhanden sind |
| 85 | comment | `ces/ontology_generator.py:383:16:COMMENT` | TOO_LONG: ratio=5.33 | 计算需要移除多少个 | Berechne, wie viele Typen entfernt werden müssen |
| 85 | comment | `ices/ontology_generator.py:391:8:COMMENT` | TOO_LONG: ratio=5.12 | 最终确保不超过限制（防御性编程） | Stelle sicher, dass die Grenze nicht überschritten wird (def |
| 85 | comment | `p/services/report_agent.py:347:8:COMMENT` | TOO_LONG: ratio=5.08 | 使用与控制台相同的简洁格式 | Verwende die gleiche einfache Formatierung wie das Konsolenf |
| 85 | comment | `p/services/report_agent.py:354:8:COMMENT` | PROTECTED_TERM_MISSING: logger | 添加到 report_agent 相关的 logger | Füge zum report_agent-Logger hinzu |
| 85 | comment | `/services/report_agent.py:362:12:COMMENT` | TOO_LONG: ratio=5.50 | 避免重复添加 | Verhindere doppelte Hinzufügungen |
| 85 | comment | `/services/report_agent.py:1090:8:COMMENT` | PROTECTED_TERM_MISSING: JSON | 只在格式1未匹配时尝试，避免误匹配正文中的 JSON | Versuche nur bei Format 1, um Missmatches im Text zu vermeid |

---
Generated from 1768 translation entries.
