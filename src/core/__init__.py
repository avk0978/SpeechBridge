#!/usr/bin/env python3
"""
Core модуль Video-Translator
Основные компоненты для обработки видео и аудио
"""

from .video_processor import VideoProcessor
from .audio_processor import AudioProcessor
from .speech_recognizer import SpeechRecognizer
from .speech_synthesizer import SpeechSynthesizer

__all__ = [
    'VideoProcessor',
    'AudioProcessor', 
    'SpeechRecognizer',
    'SpeechSynthesizer'
]

__version__ = "1.0.0"

def get_core_modules():
    """Получение списка доступных core модулей"""
    return {
        'VideoProcessor': VideoProcessor,
        'AudioProcessor': AudioProcessor,
        'SpeechRecognizer': SpeechRecognizer,
        'SpeechSynthesizer': SpeechSynthesizer
    }

def test_all_modules():
    """Тестирование всех core модулей"""
    results = {}
    
    modules = get_core_modules()
    
    for name, module_class in modules.items():
        try:
            instance = module_class()
            results[name] = {'status': 'success', 'instance': instance}
            print(f"✅ {name}: инициализирован успешно")
        except Exception as e:
            results[name] = {'status': 'error', 'error': str(e)}
            print(f"❌ {name}: ошибка инициализации - {e}")
    
    return results

if __name__ == "__main__":
    print("=== Тестирование Core модулей ===")
    test_all_modules()
