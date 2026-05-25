#!/usr/bin/env python3
"""
Batch-Translation: Chinese → German for all backend Python files.
Applies phrase-based replacement sorted by length (longest first).
Run multiple times as the dictionary grows.

Usage: python scripts/translate_backend.py [--dry-run] [--file PATH]
"""
import re
import os
import sys

# Comprehensive Chinese→German phrase dictionary
# Sorted by length (longest first) at runtime to avoid partial matches
TRANSLATIONS = {
    # ===== Multi-word phrases (longest first) =====
    "你对这件事有什么看法？": "Was halten Sie davon?",
    "同时采访两个平台": "beide Plattformen gleichzeitig interviewen",
    "可选，超时时间（秒），默认": "optional, Timeout in Sekunden, Standard",
    "需要重试的异常类型": "Exception-Typen die Retry auslösen",
    "模拟需求描述": "Simulationsanforderungs-Beschreibung",
    "次重试后仍失败": " Retries fehlgeschlagen",
    "次尝试失败": " Versuche fehlgeschlagen",
    "检查文件是否存在": "Prüfen ob Datei existiert",
    "添加前缀避免": "Prefix hinzufügen um zu vermeiden",
    "从配置文件获取": "Aus Konfigurationsdatei laden",
    "确保目录存在": "Verzeichnis sicherstellen",
    "创建异步任务": "Async-Task erstellen",
    "启动后台线程": "Hintergrund-Thread starten",
    "更新模拟状态": "Simulationsstatus aktualisieren",
    "检查环境状态": "Umgebungsstatus prüfen",
    "超时时间（秒）": "Timeout (Sekunden)",
    "搜索查询": "Such-Query",
    "搜索结果": "Suchergebnis",
    "进度回调函数": "Fortschritts-Callback",
    "模拟不存在": "Simulation existiert nicht",
    "错误信息": "Fehlermeldung",
    "动作日志": "Aktions-Log",
    "事件配置": "Event-Konfiguration",
    "时间配置": "Zeitkonfiguration",
    "平台配置": "Plattformkonfiguration",
    "平台类型（": "Plattformtyp (",
    "模拟需求": "Simulationsanforderung",
    "报告大纲": "Berichts-Gliederung",
    "执行摘要": "Executive Summary",
    "完整报告": "Vollständiger Bericht",
    "分批生成": "in Batches generieren",
    "过滤轮次": "Runden filtern",
    "过滤平台（": "Plattform filtern (",
    "历史": "Verlauf",
    "是否启用": "ob aktiviert",
    "默认只采访": "Standard: nur interviewen",
    "获取图谱": "Graph abrufen",
    "不指定": "nicht angegeben",
    "秒后重试": "s warten, Retry",
    "返回内容】": "Rückgabe-Inhalt]",
    "使用场景】": "Anwendungsfall]",
    "转换为字典": "in Dict konvertieren",
    "检测编码": "Encoding erkennen",
    "原始文本": "Originaltext",
    "构建图谱": "Graph aufbauen",
    "设置本体": "Ontologie setzen",
    "个实体类型": " Entitätstypen",
    "未配置": "nicht konfiguriert",
    "只采访": "nur interviewen",
    "文件路径": "Dateipfad",
    "调用工具": "Tool aufrufen",
    "可选，默认": "optional, Standard",

    # ===== Common domain terms =====
    "配置文件": "Konfigurationsdatei",
    "数据库": "Datenbank",
    "模拟": "Simulation",
    "图谱": "Graph",
    "环境": "Umgebung",
    "进程": "Prozess",
    "日志": "Log",
    "参数": "Parameter",
    "报告": "Bericht",
    "章节": "Abschnitt",
    "采访": "Interview",
    "大纲": "Gliederung",
    "实体": "Entität",
    "节点": "Knoten",
    "轮次": "Runde",
    "平台": "Plattform",
    "记忆": "Erinnerung",
    "本体": "Ontologie",
    "智能": "intelligent",
    "对话": "Dialog",
    "命令": "Kommando",
    "任务": "Task",
    "项目": "Projekt",
    "阶段": "Phase",
    "字段": "Feld",
    "格式": "Format",
    "问题": "Frage",
    "偏移量": "Offset",
    "数组": "Array",
    "晚间": "Abend",
    "分钟": "Minuten",
    "分页": "Paginierung",
    "管理器": "Manager",
    "客户端": "Client",
    "响应": "Response",
    "编码": "Encoding",
    "字典": "Dictionary",
    "标记": "markieren",
    "人设": "Persona",
    "覆盖": "überschreiben",
    "字符": "Zeichen",

    # ===== Verbs / short phrases =====
    "使用": "verwenden",
    "获取": "abrufen",
    "失败": "fehlgeschlagen",
    "配置": "Konfiguration",
    "读取": "lesen",
    "调用": "aufrufen",
    "返回": "zurückgeben",
    "创建": "erstellen",
    "删除": "löschen",
    "更新": "aktualisieren",
    "设置": "setzen",
    "检查": "prüfen",
    "加载": "laden",
    "保存": "speichern",
    "发送": "senden",
    "接收": "empfangen",
    "处理": "verarbeiten",
    "执行": "ausführen",
    "生成": "generieren",
    "过滤": "filtern",
    "构建": "aufbauen",
    "验证": "validieren",
    "确保": "sicherstellen",
    "支持": "unterstützen",
    "优化": "optimieren",
    "测试": "Test",
    "等待": "warten",
    "完成": "abgeschlossen",
    "启动": "starten",
    "关闭": "schließen",
    "停止": "stoppen",
    "终止": "terminieren",

    # ===== Connectors / structure =====
    "返回：": "Returns:",
    "参数：": "Parameter:",
    "可选：": "Optional:",
    "必填，": "Pflicht, ",
    "可选": "optional",
    "默认": "Standard",
    "未知": "unbekannt",
    "如果": "falls",
    "通过": "via",
    "记录": "aufzeichnen",
    "文件": "Datei",
    "路径": "Pfad",
    "目录": "Verzeichnis",
    "状态": "Status",
    "类型": "Typ",
    "对象": "Objekt",
    "接口": "Schnittstelle",
    "请求（": "Request (",
    "错误": "Fehler",
    "信息": "Info",
    "列表": "Liste",
    "内容": "Inhalt",
    "需求": "Anforderung",
    "名称": "Name",
    "描述": "Beschreibung",

    # ===== Single-char connectors (apply last) =====
    # These are risky - only apply if surrounded by non-Chinese
}

def translate_file(filepath, dry_run=False):
    """Translate Chinese phrases in a file to German."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if not re.search(r'[\u4e00-\u9fff]', content):
        return 0

    original = content
    
    # Sort by length (longest first) to avoid partial matches
    sorted_translations = sorted(TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True)
    
    for cn, de in sorted_translations:
        content = content.replace(cn, de)

    if content != original and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    remaining = len(re.findall(r'[\u4e00-\u9fff]+', content))
    return remaining


def main():
    dry_run = '--dry-run' in sys.argv
    single_file = None
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        single_file = sys.argv[idx + 1]

    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
    
    total_remaining = 0
    for dirpath, _, fnames in os.walk(root):
        if '.venv' in dirpath:
            continue
        for f in sorted(fnames):
            if not f.endswith('.py'):
                continue
            fp = os.path.join(dirpath, f)
            if single_file and single_file not in fp:
                continue
            remaining = translate_file(fp, dry_run)
            if remaining > 0:
                rel = os.path.relpath(fp, root)
                print(f"  {rel}: {remaining} remaining")
                total_remaining += remaining

    print(f"\nTotal remaining Chinese groups: {total_remaining}")
    if dry_run:
        print("(dry-run mode, no files modified)")


if __name__ == '__main__':
    main()
