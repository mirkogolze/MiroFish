"""
Dateiparser-Werkzeug
Unterstützt die Textextraktion aus PDF-, Markdown- und TXT-Dateien.
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    Lese eine Textdatei, UTF-8 fehlschlägt wird die Kodierung automatisch erkannt.
    
    Verwende mehrstufige Rückfallstrategie:
    1. Versuche zuerst UTF-8-Decodierung
    2. Nutze charset_normalizer zur Erkennung der Kodierung
    3. Falle zurück auf chardet zur Erkennung der Kodierung
    4. Letzte Sicherheit: UTF-8 + errors='replace'
    
    Args:
        file_path: Dateipfad
    
    Returns:
        Entschlüsselte Textinhalte.
    """
    data = Path(file_path).read_bytes()
    
    # Versuchen, UTF-8 zu verwenden
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # Versuchen, die Kodierung mit charset_normalizer zu ermitteln
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # Zurückfallen auf chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # Letzte Sicherung: Verwenden von UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """Dateiparser"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        Extrahiere den Text aus der Datei
        
        Args:
            file_path: Dateipfad
        
        Returns:
            Der extrahierte Textinhalt.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Datei existiert nicht: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Nicht unterstütztes Dateiformat: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        
        raise ValueError(f"Nicht verarbeitbares Dateiformat: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """Extrahiere Text aus PDF"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("Installieren Sie PyMuPDF: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Extrahiere Text aus Markdown, unterstützt automatische Codierungserkennung"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """Extrahiere Text aus TXT, unterstützt automatische Codierungserkennung"""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        Extrahiere den Text aus mehreren Dateien und kombiniere sie.
        
        Args:
            file_paths: Liste der Dateipfade
        
        Returns:
            Der kombinierte Text.
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== Dokument {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== Dokument {i}: {file_path} (Extraktion fehlgeschlagen: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    Teile den Text in kleinere Blöcke auf.
    
    Args:
        text: Originaltext
        chunk_size: Anzahl der Zeichen pro Block
        overlap: Anzahl der überlappenden Zeichen
        
    Returns:
        Liste von Textblöcken.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Versuchen, die Trennung an Satzgrenzen durchzuführen
        if end < len(text):
            # Suchen des nächsten Satzeschließers
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Der nächste Block beginnt an der Überschneidungsposition
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

