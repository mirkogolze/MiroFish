/**
 * i18n Migration Script
 * Replaces hardcoded Chinese strings in Vue/JS files with $t() / t() calls
 * and adds corresponding keys to de.json and en.json
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const LOCALES_DIR = path.join(ROOT, 'locales')
const SRC_DIR = path.join(ROOT, 'frontend/src')

// Load existing locale files
const deJson = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, 'de.json'), 'utf-8'))
const enJson = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, 'en.json'), 'utf-8'))

// ============================================================
// MAPPING: Chinese string → { key, de, en }
// ============================================================
const newKeys = {
  // --- Process.vue template ---
  process: {
    stepName: { de: 'Graph-Aufbau', en: 'Graph Build' },
    realtimeGraph: { de: 'Echtzeit-Wissensgraph', en: 'Real-time Knowledge Graph' },
    nodes: { de: 'Knoten', en: 'Nodes' },
    relations: { de: 'Relationen', en: 'Relations' },
    refreshGraph: { de: 'Graph aktualisieren', en: 'Refresh Graph' },
    exitFullscreen: { de: 'Vollbild beenden', en: 'Exit Fullscreen' },
    enterFullscreen: { de: 'Vollbild', en: 'Fullscreen' },
    realtimeUpdating: { de: 'Echtzeit-Aktualisierung...', en: 'Updating in real-time...' },
    graphDataLoading: { de: 'Graph-Daten werden geladen...', en: 'Loading graph data...' },
    waitingOntology: { de: 'Warte auf Ontologie-Generierung', en: 'Waiting for ontology generation' },
    autoStartHint: { de: 'Graph-Aufbau startet automatisch nach Abschluss', en: 'Graph build will start automatically after completion' },
    graphBuilding: { de: 'Graph wird aufgebaut', en: 'Building graph' },
    dataShowingSoon: { de: 'Daten werden gleich angezeigt...', en: 'Data will appear shortly...' },
    buildProcess: { de: 'Aufbau-Prozess', en: 'Build Process' },
    ontologyGeneration: { de: 'Ontologie-Generierung', en: 'Ontology Generation' },
    apiDescription: { de: 'API-Beschreibung', en: 'API Description' },
    ontologyApiDesc: { de: 'Nach Dokumenten-Upload analysiert das LLM den Inhalt und generiert automatisch eine passende Ontologie-Struktur (Entitätstypen + Relationstypen)', en: 'After document upload, the LLM analyzes content and automatically generates a suitable ontology structure (entity types + relation types)' },
    generationProgress: { de: 'Generierungsfortschritt', en: 'Generation Progress' },
    generatedEntityTypes: { de: 'Generierte Entitätstypen', en: 'Generated Entity Types' },
    generatedRelationTypes: { de: 'Generierte Relationstypen', en: 'Generated Relation Types' },
    moreRelations: { de: 'weitere Relationen...', en: 'more relations...' },
    waitingOntologyHint: { de: 'Warte auf Ontologie-Generierung...', en: 'Waiting for ontology generation...' },
    graphBuild: { de: 'Graph-Aufbau', en: 'Graph Build' },
    graphApiDesc: { de: 'Basierend auf der generierten Ontologie werden Dokumente in Chunks aufgeteilt und über die Zep API ein Wissensgraph aufgebaut', en: 'Based on the generated ontology, documents are chunked and a knowledge graph is built via the Zep API' },
    waitingOntologyComplete: { de: 'Warte auf Abschluss der Ontologie-Generierung...', en: 'Waiting for ontology generation to complete...' },
    buildProgress: { de: 'Aufbau-Fortschritt', en: 'Build Progress' },
    buildResult: { de: 'Aufbau-Ergebnis', en: 'Build Result' },
    entityNodes: { de: 'Entitäts-Knoten', en: 'Entity Nodes' },
    relationEdges: { de: 'Relations-Kanten', en: 'Relation Edges' },
    entityTypes: { de: 'Entitätstypen', en: 'Entity Types' },
    buildComplete: { de: 'Aufbau abgeschlossen', en: 'Build Complete' },
    readyForNextStep: { de: 'Bereit für den nächsten Schritt', en: 'Ready for next step' },
    enterEnvSetup: { de: 'Zur Umgebungseinrichtung', en: 'Enter Environment Setup' },
    projectInfo: { de: 'Projektinformationen', en: 'Project Information' },
    projectName: { de: 'Projektname', en: 'Project Name' },
    projectId: { de: 'Projekt-ID', en: 'Project ID' },
    graphId: { de: 'Graph-ID', en: 'Graph ID' },
    simRequirement: { de: 'Simulationsanforderung', en: 'Simulation Requirement' },
    // Script section
    statusFailed: { de: 'Aufbau fehlgeschlagen', en: 'Build Failed' },
    statusComplete: { de: 'Aufbau abgeschlossen', en: 'Build Complete' },
    statusGraphBuilding: { de: 'Graph-Aufbau läuft', en: 'Building Graph' },
    statusOntologyGen: { de: 'Ontologie-Generierung', en: 'Generating Ontology' },
    statusInitializing: { de: 'Initialisierung', en: 'Initializing' },
    envSetupWip: { de: 'Umgebungseinrichtung in Entwicklung...', en: 'Environment setup in development...' },
    phaseCompleted: { de: 'Abgeschlossen', en: 'Completed' },
    phaseInProgress: { de: 'In Bearbeitung', en: 'In Progress' },
    phasePending: { de: 'Ausstehend', en: 'Pending' },
    noFilesError: { de: 'Keine Dateien zum Hochladen. Bitte zur Startseite zurückkehren.', en: 'No files to upload. Please go back to the home page.' },
    uploadingAnalyzing: { de: 'Dateien werden hochgeladen und analysiert...', en: 'Uploading files and analyzing documents...' },
    ontologyFailed: { de: 'Ontologie-Generierung fehlgeschlagen', en: 'Ontology generation failed' },
    projectInitFailed: { de: 'Projektinitialisierung fehlgeschlagen', en: 'Project initialization failed' },
    loadProjectFailed: { de: 'Projekt laden fehlgeschlagen', en: 'Failed to load project' },
    processingFailed: { de: 'Verarbeitung fehlgeschlagen', en: 'Processing failed' },
    startingGraphBuild: { de: 'Graph-Aufbau wird gestartet...', en: 'Starting graph build...' },
    graphBuildTaskStarted: { de: 'Graph-Aufbau-Task gestartet...', en: 'Graph build task started...' },
    graphBuildStartFailed: { de: 'Graph-Aufbau konnte nicht gestartet werden', en: 'Failed to start graph build' },
    processing: { de: 'Verarbeitung...', en: 'Processing...' },
    buildCompleteLoading: { de: 'Aufbau abgeschlossen, Graph wird geladen...', en: 'Build complete, loading graph...' },
    graphBuildFailed: { de: 'Graph-Aufbau fehlgeschlagen', en: 'Graph build failed' },
    waitingGraphData: { de: 'Warte auf Graph-Daten...', en: 'Waiting for graph data...' },
    unnamed: { de: 'Unbenannt', en: 'Unnamed' },
    unknown: { de: 'Unbekannt', en: 'Unknown' },
  },
  // --- Step2EnvSetup.vue (non-comment) ---
  step2extra: {
    stageGeneratePersona: { de: 'Agent-Personas generieren', en: 'Generate Agent Personas' },
    stageGenerateConfig: { de: 'Simulationskonfiguration generieren', en: 'Generate Simulation Config' },
    stagePrepareScripts: { de: 'Simulationsskripte vorbereiten', en: 'Prepare Simulation Scripts' },
  },
  // --- Step3Simulation.vue ---
  step3extra: {
    startFailed: { de: 'Start fehlgeschlagen', en: 'Start failed' },
  },
  // --- Step5Interaction.vue ---
  step5extra: {
    questioner: { de: 'Fragender', en: 'Questioner' },
    you: { de: 'Du', en: 'You' },
    chatHistoryPrompt: { de: 'Hier ist unser bisheriger Gesprächsverlauf:\\n{history}\\nMeine neue Frage lautet: {question}', en: 'Here is our previous conversation:\\n{history}\\nMy new question is: {question}' },
  },
  // --- Home.vue ---
  homeExtra: {
    selectLanguage: { de: 'Sprache wählen', en: 'Select Language' },
  },
  // --- GraphPanel.vue ---
  graphExtra: {
    entityType: { de: 'Entitätstyp', en: 'Entity Type' },
    factType: { de: 'Faktentyp', en: 'Fact Type' },
  },
  // --- HistoryDatabase.vue ---
  historyExtra: {
    loading: { de: 'Laden...', en: 'Loading...' },
    noHistory: { de: 'Keine Simulationshistorie vorhanden', en: 'No simulation history available' },
    created: { de: 'Erstellt', en: 'Created' },
    status: { de: 'Status', en: 'Status' },
    deleteConfirm: { de: 'Möchtest du diese Simulation wirklich löschen?', en: 'Are you sure you want to delete this simulation?' },
    deleteFailed: { de: 'Löschen fehlgeschlagen', en: 'Delete failed' },
    deleted: { de: 'Erfolgreich gelöscht', en: 'Successfully deleted' },
    loadFailed: { de: 'Historie laden fehlgeschlagen', en: 'Failed to load history' },
    untitled: { de: 'Unbenannte Simulation', en: 'Untitled Simulation' },
    simulationStatus: {
      created: { de: 'Erstellt', en: 'Created' },
      ontology_generated: { de: 'Ontologie generiert', en: 'Ontology Generated' },
      graph_building: { de: 'Graph wird aufgebaut', en: 'Building Graph' },
      graph_completed: { de: 'Graph abgeschlossen', en: 'Graph Completed' },
      preparing: { de: 'Wird vorbereitet', en: 'Preparing' },
      prepared: { de: 'Vorbereitet', en: 'Prepared' },
      running: { de: 'Läuft', en: 'Running' },
      completed: { de: 'Abgeschlossen', en: 'Completed' },
      failed: { de: 'Fehlgeschlagen', en: 'Failed' },
    },
  },
  // --- Step4Report.vue ---
  step4extra: {
    reasonLabel: { de: 'Begründung', en: 'Reasoning' },
    waitingStart: { de: 'Warte auf Start', en: 'Waiting to start' },
    noReplyPlatform: { de: '(Diese Plattform hat keine Antwort erhalten)', en: '(No reply received from this platform)' },
    errorLevel: { de: 'Fehler', en: 'Error' },
    warningLevel: { de: 'Warnung', en: 'Warning' },
    reportLoading: { de: 'Report wird geladen...', en: 'Loading report...' },
    reportEmpty: { de: 'Kein Report-Inhalt verfügbar', en: 'No report content available' },
    generatingHint: { de: 'Report wird generiert...', en: 'Generating report...' },
    sectionTitle: { de: 'Abschnitt', en: 'Section' },
    toolCallLabel: { de: 'Tool-Aufruf', en: 'Tool Call' },
    toolResultLabel: { de: 'Tool-Ergebnis', en: 'Tool Result' },
    thinkingLabel: { de: 'Denkt nach...', en: 'Thinking...' },
    writingLabel: { de: 'Schreibt...', en: 'Writing...' },
  },
  // --- backend ---
  backendExtra: {
    configError: { de: 'Konfigurationsfehler', en: 'Configuration error' },
    checkEnvFile: { de: 'Bitte prüfe die .env-Datei', en: 'Please check the .env file' },
    fileNotExist: { de: 'Datei existiert nicht', en: 'File does not exist' },
    unsupportedFormat: { de: 'Nicht unterstütztes Dateiformat', en: 'Unsupported file format' },
    unprocessableFormat: { de: 'Nicht verarbeitbares Dateiformat', en: 'Unprocessable file format' },
    pymuPdfRequired: { de: 'PyMuPDF muss installiert werden', en: 'PyMuPDF needs to be installed' },
    documentLabel: { de: 'Dokument {i}: {filename}', en: 'Document {i}: {filename}' },
    extractionFailed: { de: 'Extraktion fehlgeschlagen', en: 'Extraction failed' },
  }
}

// ============================================================
// Add new keys to locale files
// ============================================================
function mergeKeys(target, source, prefix = '') {
  for (const [key, val] of Object.entries(source)) {
    if (val.de !== undefined && val.en !== undefined) {
      // leaf node
      if (!target[prefix]) target[prefix] = {}
      target[prefix][key] = val
    } else if (typeof val === 'object') {
      mergeKeys(target, val, prefix ? `${prefix}.${key}` : key)
    }
  }
}

// Add process section to de.json
if (!deJson.process) deJson.process = {}
for (const [key, val] of Object.entries(newKeys.process)) {
  deJson.process[key] = val.de
}

// Add process section to en.json
if (!enJson.process) enJson.process = {}
for (const [key, val] of Object.entries(newKeys.process)) {
  enJson.process[key] = val.en
}

// Add other sections
for (const section of ['step2extra', 'step3extra', 'step5extra', 'homeExtra', 'graphExtra', 'historyExtra', 'step4extra', 'backendExtra']) {
  if (!deJson[section]) deJson[section] = {}
  if (!enJson[section]) enJson[section] = {}
  
  function addNested(obj, deTarget, enTarget) {
    for (const [key, val] of Object.entries(obj)) {
      if (val.de !== undefined && val.en !== undefined) {
        deTarget[key] = val.de
        enTarget[key] = val.en
      } else if (typeof val === 'object') {
        if (!deTarget[key]) deTarget[key] = {}
        if (!enTarget[key]) enTarget[key] = {}
        addNested(val, deTarget[key], enTarget[key])
      }
    }
  }
  addNested(newKeys[section], deJson[section], enJson[section])
}

// Write updated locale files
fs.writeFileSync(path.join(LOCALES_DIR, 'de.json'), JSON.stringify(deJson, null, 2) + '\n', 'utf-8')
fs.writeFileSync(path.join(LOCALES_DIR, 'en.json'), JSON.stringify(enJson, null, 2) + '\n', 'utf-8')
console.log('✅ Locale files updated (de.json + en.json)')

// ============================================================
// REPLACEMENTS in Vue files
// ============================================================

function replaceInFile(filePath, replacements) {
  let content = fs.readFileSync(filePath, 'utf-8')
  let count = 0
  
  for (const [search, replace] of replacements) {
    const before = content
    if (search instanceof RegExp) {
      content = content.replace(search, replace)
    } else {
      content = content.split(search).join(replace)
    }
    if (content !== before) count++
  }
  
  fs.writeFileSync(filePath, content, 'utf-8')
  console.log(`  ${path.relative(ROOT, filePath)}: ${count} replacements`)
  return count
}

// --- Process.vue ---
const processVue = path.join(SRC_DIR, 'views/Process.vue')
replaceInFile(processVue, [
  // Template: Add useI18n import if not present
  // Add i18n import to script setup
  [`import * as d3 from 'd3'`, `import * as d3 from 'd3'\nimport { useI18n } from 'vue-i18n'\n\nconst { t } = useI18n()`],
  
  // Template strings
  [`<div class="step-name">图谱构建</div>`, `<div class="step-name">{{ t('process.stepName') }}</div>`],
  [`<span class="header-title">实时知识图谱</span>`, `<span class="header-title">{{ t('process.realtimeGraph') }}</span>`],
  [/(\d+\s*\}\}\s*)节点/g, `$1{{ t('process.nodes') }}`],
  [/(\d+\s*\}\}\s*)关系/g, `$1{{ t('process.relations') }}`],
  [`}} 节点`, `}} {{ t('process.nodes') }}`],
  [`}} 关系`, `}} {{ t('process.relations') }}`],
  [`title="刷新图谱"`, `:title="t('process.refreshGraph')"`],
  [`'退出全屏' : '全屏显示'`, `t('process.exitFullscreen') : t('process.enterFullscreen')`],
  [`实时更新中...`, `{{ t('process.realtimeUpdating') }}`],
  [`<p class="loading-text">图谱数据加载中...</p>`, `<p class="loading-text">{{ t('process.graphDataLoading') }}</p>`],
  [`<p class="waiting-text">等待本体生成</p>`, `<p class="waiting-text">{{ t('process.waitingOntology') }}</p>`],
  [`<p class="waiting-hint">生成完成后将自动开始构建图谱</p>`, `<p class="waiting-hint">{{ t('process.autoStartHint') }}</p>`],
  [`<p class="waiting-text">图谱构建中</p>`, `<p class="waiting-text">{{ t('process.graphBuilding') }}</p>`],
  [`<p class="waiting-hint">数据即将显示...</p>`, `<p class="waiting-hint">{{ t('process.dataShowingSoon') }}</p>`],
  [`<span class="header-title">构建流程</span>`, `<span class="header-title">{{ t('process.buildProcess') }}</span>`],
  [`<div class="phase-title">本体生成</div>`, `<div class="phase-title">{{ t('process.ontologyGeneration') }}</div>`],
  [`<div class="detail-label">接口说明</div>\n                <div class="detail-content">\n                  上传文档后，LLM分析文档内容，自动生成适合舆论模拟的本体结构（实体类型 + 关系类型）`, `<div class="detail-label">{{ t('process.apiDescription') }}</div>\n                <div class="detail-content">\n                  {{ t('process.ontologyApiDesc') }}`],
  [`<div class="detail-label">生成进度</div>`, `<div class="detail-label">{{ t('process.generationProgress') }}</div>`],
  [`<div class="detail-label">生成的实体类型`, `<div class="detail-label">{{ t('process.generatedEntityTypes') }}`],
  [`<div class="detail-label">生成的关系类型`, `<div class="detail-label">{{ t('process.generatedRelationTypes') }}`],
  [`更多关系...`, `{{ t('process.moreRelations') }}`],
  [`<div class="waiting-hint">等待本体生成...</div>`, `<div class="waiting-hint">{{ t('process.waitingOntologyHint') }}</div>`],
  [`<div class="phase-title">图谱构建</div>`, `<div class="phase-title">{{ t('process.graphBuild') }}</div>`],
  [`<div class="detail-label">接口说明</div>\n                <div class="detail-content">\n                  基于生成的本体，将文档分块后调用 Zep API 构建知识图谱，提取实体和关系`, `<div class="detail-label">{{ t('process.apiDescription') }}</div>\n                <div class="detail-content">\n                  {{ t('process.graphApiDesc') }}`],
  [`<div class="waiting-hint">等待本体生成完成...</div>`, `<div class="waiting-hint">{{ t('process.waitingOntologyComplete') }}</div>`],
  [`<div class="detail-label">构建进度</div>`, `<div class="detail-label">{{ t('process.buildProgress') }}</div>`],
  [`<div class="detail-label">构建结果</div>`, `<div class="detail-label">{{ t('process.buildResult') }}</div>`],
  [`<span class="result-label">实体节点</span>`, `<span class="result-label">{{ t('process.entityNodes') }}</span>`],
  [`<span class="result-label">关系边</span>`, `<span class="result-label">{{ t('process.relationEdges') }}</span>`],
  [`<span class="result-label">实体类型</span>`, `<span class="result-label">{{ t('process.entityTypes') }}</span>`],
  [`<div class="phase-title">构建完成</div>`, `<div class="phase-title">{{ t('process.buildComplete') }}</div>`],
  [`<div class="phase-api">准备进入下一步骤</div>`, `<div class="phase-api">{{ t('process.readyForNextStep') }}</div>`],
  [`进入环境搭建`, `{{ t('process.enterEnvSetup') }}`],
  [`<span class="project-title">项目信息</span>`, `<span class="project-title">{{ t('process.projectInfo') }}</span>`],
  [`<span class="item-label">项目名称</span>`, `<span class="item-label">{{ t('process.projectName') }}</span>`],
  [`<span class="item-label">项目ID</span>`, `<span class="item-label">{{ t('process.projectId') }}</span>`],
  [`<span class="item-label">图谱ID</span>`, `<span class="item-label">{{ t('process.graphId') }}</span>`],
  [`<span class="item-label">模拟需求</span>`, `<span class="item-label">{{ t('process.simRequirement') }}</span>`],
  
  // Script section
  [`if (error.value) return '构建失败'`, `if (error.value) return t('process.statusFailed')`],
  [`if (currentPhase.value >= 2) return '构建完成'`, `if (currentPhase.value >= 2) return t('process.statusComplete')`],
  [`if (currentPhase.value === 1) return '图谱构建中'`, `if (currentPhase.value === 1) return t('process.statusGraphBuilding')`],
  [`if (currentPhase.value === 0) return '本体生成中'`, `if (currentPhase.value === 0) return t('process.statusOntologyGen')`],
  [`return '初始化中'`, `return t('process.statusInitializing')`],
  [`alert('环境搭建功能开发中...')`, `alert(t('process.envSetupWip'))`],
  [`toLocaleString('zh-CN'`, `toLocaleString('de-DE'`],
  [`if (currentPhase.value > phase) return '已完成'`, `if (currentPhase.value > phase) return t('process.phaseCompleted')`],
  [`return '进行中'`, `return t('process.phaseInProgress')`],
  [`return '等待中'`, `return t('process.phasePending')`],
  [`error.value = '没有待上传的文件，请返回首页重新操作'`, `error.value = t('process.noFilesError')`],
  [`ontologyProgress.value = { message: '正在上传文件并分析文档...' }`, `ontologyProgress.value = { message: t('process.uploadingAnalyzing') }`],
  [`error.value = response.error || '本体生成失败'`, `error.value = response.error || t('process.ontologyFailed')`],
  [`error.value = '项目初始化失败: ' + (err.message || '未知错误')`, `error.value = t('process.projectInitFailed') + ': ' + (err.message || t('process.unknown'))`],
  [`error.value = response.error || '加载项目失败'`, `error.value = response.error || t('process.loadProjectFailed')`],
  [`error.value = '加载项目失败: ' + (err.message || '未知错误')`, `error.value = t('process.loadProjectFailed') + ': ' + (err.message || t('process.unknown'))`],
  [`error.value = projectData.value?.error || '处理失败'`, `error.value = projectData.value?.error || t('process.processingFailed')`],
  [`message: '正在启动图谱构建...'`, `message: t('process.startingGraphBuild')`],
  [`buildProgress.value.message = '图谱构建任务已启动...'`, `buildProgress.value.message = t('process.graphBuildTaskStarted')`],
  [`error.value = response.error || '启动图谱构建失败'`, `error.value = response.error || t('process.graphBuildStartFailed')`],
  [`error.value = '启动图谱构建失败: ' + (err.message || '未知错误')`, `error.value = t('process.graphBuildStartFailed') + ': ' + (err.message || t('process.unknown'))`],
  [`message: task.message || '处理中...'`, `message: task.message || t('process.processing')`],
  [`message: '构建完成，正在加载图谱...'`, `message: t('process.buildCompleteLoading')`],
  [`error.value = '图谱构建失败: ' + (task.error || '未知错误')`, `error.value = t('process.graphBuildFailed') + ': ' + (task.error || t('process.unknown'))`],
  [`.text('等待图谱数据...')`, `.text(t('process.waitingGraphData'))`],
  [`name: n.name || '未命名'`, `name: n.name || t('process.unnamed')`],
  [`source_name: nodeMap[e.source_node_uuid]?.name || '未知'`, `source_name: nodeMap[e.source_node_uuid]?.name || t('process.unknown')`],
  [`target_name: nodeMap[e.target_node_uuid]?.name || '未知'`, `target_name: nodeMap[e.target_node_uuid]?.name || t('process.unknown')`],
])

// --- Step2EnvSetup.vue ---
const step2Vue = path.join(SRC_DIR, 'components/Step2EnvSetup.vue')
let step2Content = fs.readFileSync(step2Vue, 'utf-8')

// Stage comparisons — these compare against backend progress messages
// We need to replace the Chinese comparison strings
step2Content = step2Content.replace(/=== '生成Agent人设'/g, "=== 'generating_profiles'")
step2Content = step2Content.replace(/=== '生成模拟配置'/g, "=== 'generating_config'")
step2Content = step2Content.replace(/=== '准备模拟脚本'/g, "=== 'preparing_scripts'")
// Also handle includes/indexOf patterns
step2Content = step2Content.replace(/'生成Agent人设'/g, "'generating_profiles'")
step2Content = step2Content.replace(/'生成模拟配置'/g, "'generating_config'")
step2Content = step2Content.replace(/'准备模拟脚本'/g, "'preparing_scripts'")

fs.writeFileSync(step2Vue, step2Content, 'utf-8')
console.log(`  frontend/src/components/Step2EnvSetup.vue: stage strings replaced`)

// --- Step3Simulation.vue ---
const step3Vue = path.join(SRC_DIR, 'components/Step3Simulation.vue')
replaceInFile(step3Vue, [
  [`|| '启动失败'`, `|| t('step3extra.startFailed')`],
])

// --- Step5Interaction.vue ---
const step5Vue = path.join(SRC_DIR, 'components/Step5Interaction.vue')
let step5Content = fs.readFileSync(step5Vue, 'utf-8')

// Replace the chat prompt builder
step5Content = step5Content.replace(
  /提问者/g,
  'Questioner'
)
step5Content = step5Content.replace(
  /以下是我们之前的对话[：:]\n/g,
  'Here is our previous conversation:\\n'
)
step5Content = step5Content.replace(
  /现在我的新问题是[：:]/g,
  'My new question is: '
)
// The 你 in context
step5Content = step5Content.replace(
  /role:\s*'你'/g,
  "role: 'You'"
)

fs.writeFileSync(step5Vue, step5Content, 'utf-8')
console.log(`  frontend/src/components/Step5Interaction.vue: prompt strings replaced`)

// --- Home.vue ---
const homeVue = path.join(SRC_DIR, 'views/Home.vue')
let homeContent = fs.readFileSync(homeVue, 'utf-8')
// Replace locale display names that aren't coming from i18n
homeContent = homeContent.replace(/'zh-CN'/g, "'de-DE'")
fs.writeFileSync(homeVue, homeContent, 'utf-8')
console.log(`  frontend/src/views/Home.vue: locale refs updated`)

// --- Backend locale.py format date ---
const localePy = path.join(ROOT, 'backend/app/utils/locale.py')
// Already fixed in prior step

// --- Backend file_parser.py ---
const fileParserPy = path.join(ROOT, 'backend/app/utils/file_parser.py')
if (fs.existsSync(fileParserPy)) {
  let fpContent = fs.readFileSync(fileParserPy, 'utf-8')
  fpContent = fpContent.replace(/文件不存在/g, 'File does not exist')
  fpContent = fpContent.replace(/不支持的文件格式/g, 'Unsupported file format')
  fpContent = fpContent.replace(/无法处理的文件格式/g, 'Unprocessable file format')
  fpContent = fpContent.replace(/需要安装PyMuPDF/g, 'PyMuPDF needs to be installed')
  fpContent = fpContent.replace(/提取失败/g, 'Extraction failed')
  fpContent = fpContent.replace(/文档\s*\{/g, 'Document {')
  fs.writeFileSync(fileParserPy, fpContent, 'utf-8')
  console.log(`  backend/app/utils/file_parser.py: error messages translated`)
}

// --- Backend config.py ---
const configPy = path.join(ROOT, 'backend/app/config.py')
if (fs.existsSync(configPy)) {
  let cfgContent = fs.readFileSync(configPy, 'utf-8')
  cfgContent = cfgContent.replace(/LLM_API_KEY 未配置/g, 'LLM_API_KEY not configured')
  cfgContent = cfgContent.replace(/ZEP_API_KEY 未配置/g, 'ZEP_API_KEY not configured')
  cfgContent = cfgContent.replace(/未配置/g, 'not configured')
  fs.writeFileSync(configPy, cfgContent, 'utf-8')
  console.log(`  backend/app/config.py: error messages translated`)
}

console.log('\n✅ i18n migration complete!')
console.log('⚠️  NOTE: Step4Report.vue, HistoryDatabase.vue, and GraphPanel.vue still need manual review for remaining strings.')
console.log('   Run: perl -CSD -ne \'print "$.: $_" if /[\\x{4e00}-\\x{9fff}]/\' <file> to check remaining Chinese.')
