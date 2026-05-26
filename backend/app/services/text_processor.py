"""
Textverarbeitungsdienst
"""

from typing import List, Optional
from ..utils.file_parser import FileParser, split_text_into_chunks


class TextProcessor:
    """Textverarbeiter"""
    
    @staticmethod
    def extract_from_files(file_paths: List[str]) -> str:
        """Extrahiere Text aus mehreren Dateien"""
        return FileParser.extract_from_multiple(file_paths)
    
    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        Teile den Text in Blöcke auf.
        
        Args:
            text: Originaltext
            chunk_size: Blockgröße
            overlap: Überlappungsgroße
            
        Returns:
            Eine Liste mit den Textblöcken
        """
        return split_text_into_chunks(text, chunk_size, overlap)
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        Vorbearbeitung des Textes.
        - Entferne unnötige Leerzeichen.
        - Standardisiere Zeilenumbrüche.
        
        Args:
            text: Originaltext
            
        Returns:
            Der vorbearbeitete Text
        """
        import re
        
        # Standardisiere Zeilenumbrüche
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Entferne mehrere leere Zeilen (behalte maximal zwei)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Entferne Leerzeichen am Anfang und Ende jeder Zeile
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    @staticmethod
    def get_text_stats(text: str) -> dict:
        """Hole Textstatistiken"""
        return {
            "total_chars": len(text),
            "total_lines": text.count('\n') + 1,
            "total_words": len(text.split()),
        }

