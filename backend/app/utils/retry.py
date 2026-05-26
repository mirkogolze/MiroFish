"""
API-Aufruf-Wiederholungsmechanismus
Für die Wiederholung von Aufrufen an externe APIs wie LLM usw.
"""

import time
import random
import functools
from typing import Callable, Any, Optional, Type, Tuple
from ..utils.logger import get_logger

logger = get_logger('mirofish.retry')


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
Versuchsdekorator mit exponentieller Rückzugspolitik

Args:
max_retries: Maximale Anzahl der Wiederholungen
initial_delay: Initiale Verzögerung (Sekunden)
max_delay: Maximale Verzögerung (Sekunden)
backoff_factor: Faktor für den Rückzug
jitter: Ob zufällige Jitter hinzugefügt werden sollen
exceptions: Ausnahmetypen, die wiederholt werden sollen
on_retry: Aufruffunktion bei Wiederholung (exception, retry_count)

Verwendung:
@retry_with_backoff(max_retries=3)
def call_llm_api():
    ...
"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Funktion {func.__name__} bei {max_retries} Wiederholungen ohne Erfolg: {str(e)}")
                        raise
                    
                    # Berechne die Verzögerung
                    current_delay = min(delay, max_delay)
                    if jitter:
                        current_delay = current_delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Funktion {func.__name__} Nr. {attempt + 1} Versuche fehlgeschlagen: {str(e)}, "
                        f"{current_delay:.1f} Sek. erneut versuchen..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    time.sleep(current_delay)
                    delay *= backoff_factor
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_backoff_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
Asynchroner Version von Wiederholungsdekorator
"""
    import asyncio
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Async-Funktion {func.__name__} bei {max_retries} Wiederholungen ohne Erfolg: {str(e)}")
                        raise
                    
                    current_delay = min(delay, max_delay)
                    if jitter:
                        current_delay = current_delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Async-Funktion {func.__name__} Nr. {attempt + 1} Versuche fehlgeschlagen: {str(e)}, "
                        f"{current_delay:.1f} Sek. erneut versuchen..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    await asyncio.sleep(current_delay)
                    delay *= backoff_factor
            
            raise last_exception
        
        return wrapper
    return decorator


class RetryableAPIClient:
    """
API-Client-Kapselung mit Wiederholungslogik
"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def call_with_retry(
        self,
        func: Callable,
        *args,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        **kwargs
    ) -> Any:
        """
Funktionsaufrufe ausführen und bei Fehlern wiederholen

Args:
func: Aufrufende Funktion
*args: Parameter für die Funktion
exceptions: Ausnahmetypen, die wiederholt werden sollen
**kwargs: Schlüsselwort-Parameter für die Funktion

Returns:
Funktionsrückgabewert
"""
        last_exception = None
        delay = self.initial_delay
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
                
            except exceptions as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    logger.error(f"API-Aufruf bei {self.max_retries} Wiederholungen ohne Erfolg: {str(e)}")
                    raise
                
                current_delay = min(delay, self.max_delay)
                current_delay = current_delay * (0.5 + random.random())
                
                logger.warning(
                    f"API-Aufruf Nr. {attempt + 1} Versuche fehlgeschlagen: {str(e)}, "
                    f"{current_delay:.1f} Sek. erneut versuchen..."
                )
                
                time.sleep(current_delay)
                delay *= self.backoff_factor
        
        raise last_exception
    
    def call_batch_with_retry(
        self,
        items: list,
        process_func: Callable,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        continue_on_failure: bool = True
    ) -> Tuple[list, list]:
        """
Batch-Aufrufe durchführen und einzelne Fehlschläge wiederholen

Args:
items: Liste der zu verarbeitenden Elemente
process_func: Verarbeitungsfunktion, die ein einzelnes item als Parameter erhält
exceptions: Ausnahmetypen, die wiederholt werden sollen
continue_on_failure: Ob nach einem Fehlschlag bei einem Item das Verarbeiten weitergeht

Returns:
(Teil der erfolgreichen Ergebnisse, Liste der fehlgeschlagenen Elemente)
"""
        results = []
        failures = []
        
        for idx, item in enumerate(items):
            try:
                result = self.call_with_retry(
                    process_func,
                    item,
                    exceptions=exceptions
                )
                results.append(result)
                
            except Exception as e:
                logger.error(f"Verarbeite Nr. {idx + 1} Fehler: {str(e)}")
                failures.append({
                    "index": idx,
                    "item": item,
                    "error": str(e)
                })
                
                if not continue_on_failure:
                    raise
        
        return results, failures

