#!/usr/bin/env python3
"""
SpeechRecognizer: Модуль распознавания речи
Поддерживает Google Speech Recognition и Whisper с fallback стратегиями
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List

import speech_recognition as sr

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import config


class SpeechRecognizer:
    """Класс для распознавания речи из аудио файлов"""
    
    def __init__(self):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.recognizer = sr.Recognizer()
        
        # Настройка параметров распознавания
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        self.recognizer.operation_timeout = None
        self.recognizer.phrase_threshold = 0.3
        
        self.logger.debug("SpeechRecognizer инициализирован")
    
    def transcribe_audio(self, audio_path: str, language: str = None) -> str:
        """
        Распознавание речи из аудио файла с fallback стратегией
        
        Args:
            audio_path: путь к аудио файлу
            language: код языка (по умолчанию из конфига)
            
        Returns:
            str: распознанный текст
        """
        if language is None:
            language = self.config.SPEECH_LANGUAGE
        
        try:
            self.logger.debug(f"Распознавание речи из {audio_path}")
            
            if not Path(audio_path).exists():
                raise FileNotFoundError(f"Аудио файл не найден: {audio_path}")
            
            # Попытка распознавания через Google Speech Recognition
            result = self._transcribe_with_google(audio_path, language)
            
            if result:
                self.logger.debug(f"Google SR успешно: '{result[:50]}...'")
                return result
            
            # Fallback на Whisper если доступен
            result = self._transcribe_with_whisper(audio_path, language)
            
            if result:
                self.logger.debug(f"Whisper успешно: '{result[:50]}...'")
                return result
            
            # Fallback на другие методы
            result = self._transcribe_with_alternative_methods(audio_path, language)
            
            return result or ""
            
        except Exception as e:
            self.logger.error(f"Ошибка распознавания речи: {e}")
            return ""
    
    def _transcribe_with_google(self, audio_path: str, language: str) -> Optional[str]:
        """
        Распознавание через Google Speech Recognition
        
        Args:
            audio_path: путь к аудио файлу
            language: код языка
            
        Returns:
            str: распознанный текст или None при ошибке
        """
        try:
            with sr.AudioFile(audio_path) as source:
                # Настройка для лучшего качества
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_data = self.recognizer.record(source)
                
                # Распознавание с API ключом если доступен
                api_key = self.config.SPEECH_API_KEY
                
                if api_key and api_key != "your_google_speech_api_key":
                    text = self.recognizer.recognize_google(
                        audio_data, 
                        key=api_key,
                        language=language,
                        show_all=False
                    )
                else:
                    # Бесплатное API без ключа
                    text = self.recognizer.recognize_google(
                        audio_data, 
                        language=language
                    )
                
                return text.strip() if text else None
                
        except sr.UnknownValueError:
            self.logger.debug("Google SR: речь не распознана")
            return None
        except sr.RequestError as e:
            self.logger.warning(f"Google SR API ошибка: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Google SR неожиданная ошибка: {e}")
            return None
    
    def _transcribe_with_whisper(self, audio_path: str, language: str) -> Optional[str]:
        """
        Распознавание через OpenAI Whisper (локально)
        
        Args:
            audio_path: путь к аудио файлу
            language: код языка
            
        Returns:
            str: распознанный текст или None при ошибке
        """
        try:
            import whisper
            
            # Загружаем модель (кэшируется автоматически)
            model_name = getattr(self.config, 'WHISPER_MODEL', 'base')
            model = whisper.load_model(model_name)
            
            # Конвертируем код языка для Whisper
            whisper_language = self._convert_language_code_for_whisper(language)
            
            # Распознавание
            result = model.transcribe(
                audio_path,
                language=whisper_language,
                task="transcribe",
                fp16=False,  # Для совместимости
                verbose=False
            )
            
            text = result.get('text', '').strip()
            
            if text:
                self.logger.debug(f"Whisper распознал: {len(text)} символов")
                return text
            
            return None
            
        except ImportError:
            self.logger.debug("Whisper не установлен, пропускаем")
            return None
        except Exception as e:
            self.logger.warning(f"Whisper ошибка: {e}")
            return None
    
    def _transcribe_with_alternative_methods(self, audio_path: str, language: str) -> Optional[str]:
        """
        Альтернативные методы распознавания речи
        
        Args:
            audio_path: путь к аудио файлу
            language: код языка
            
        Returns:
            str: распознанный текст или None при ошибке
        """
        methods = [
            self._try_sphinx,
            self._try_vosk,
            # Можно добавить другие движки
        ]
        
        for method in methods:
            try:
                result = method(audio_path, language)
                if result:
                    return result
            except Exception as e:
                self.logger.debug(f"Альтернативный метод неудачен: {e}")
                continue
        
        return None
    
    def _try_sphinx(self, audio_path: str, language: str) -> Optional[str]:
        """Попытка распознавания через PocketSphinx"""
        try:
            with sr.AudioFile(audio_path) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_sphinx(audio_data)
                return text.strip() if text else None
        except (ImportError, sr.UnknownValueError, sr.RequestError):
            return None
    
    def _try_vosk(self, audio_path: str, language: str) -> Optional[str]:
        """Попытка распознавания через Vosk"""
        try:
            import json
            import vosk
            import wave
            
            # Настройка модели Vosk (требует предварительной установки модели)
            model_path = getattr(self.config, 'VOSK_MODEL_PATH', None)
            if not model_path or not Path(model_path).exists():
                return None
            
            model = vosk.Model(model_path)
            recognizer = vosk.KaldiRecognizer(model, 16000)
            
            with wave.open(audio_path, 'rb') as wf:
                results = []
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if result.get('text'):
                            results.append(result['text'])
                
                # Финальный результат
                final_result = json.loads(recognizer.FinalResult())
                if final_result.get('text'):
                    results.append(final_result['text'])
                
                return ' '.join(results).strip() if results else None
                
        except (ImportError, Exception):
            return None
    
    def _convert_language_code_for_whisper(self, language: str) -> str:
        """
        Конвертация кода языка для Whisper
        
        Args:
            language: код языка в формате RFC 5646 (en-US)
            
        Returns:
            str: код языка для Whisper (en)
        """
        language_map = {
            'en-US': 'en',
            'en-GB': 'en',
            'ru-RU': 'ru',
            'es-ES': 'es',
            'fr-FR': 'fr',
            'de-DE': 'de',
            'it-IT': 'it',
            'pt-PT': 'pt',
            'zh-CN': 'zh',
            'ja-JP': 'ja',
            'ko-KR': 'ko'
        }
        
        # Если точное соответствие найдено
        if language in language_map:
            return language_map[language]
        
        # Попытка извлечь основной код языка
        base_language = language.split('-')[0].lower()
        return base_language if base_language in ['en', 'ru', 'es', 'fr', 'de', 'it', 'pt', 'zh', 'ja', 'ko'] else 'en'
    
    def transcribe_batch(self, audio_files: List[str], language: str = None) -> List[Dict]:
        """
        Пакетное распознавание нескольких аудио файлов
        
        Args:
            audio_files: список путей к аудио файлам
            language: код языка
            
        Returns:
            list: список результатов распознавания
        """
        results = []
        
        for i, audio_path in enumerate(audio_files):
            self.logger.info(f"Обработка файла {i+1}/{len(audio_files)}: {Path(audio_path).name}")
            
            start_time = None
            try:
                import time
                start_time = time.time()
                
                text = self.transcribe_audio(audio_path, language)
                
                processing_time = time.time() - start_time if start_time else 0
                
                result = {
                    'file_path': audio_path,
                    'text': text,
                    'success': bool(text),
                    'processing_time': processing_time,
                    'error': None
                }
                
            except Exception as e:
                result = {
                    'file_path': audio_path,
                    'text': '',
                    'success': False,
                    'processing_time': 0,
                    'error': str(e)
                }
                
                self.logger.error(f"Ошибка обработки {audio_path}: {e}")
            
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(f"Пакетная обработка завершена: {success_count}/{len(audio_files)} успешно")
        
        return results
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Получение списка поддерживаемых языков
        
        Returns:
            dict: словарь с кодами и названиями языков
        """
        return {
            'en-US': 'English (US)',
            'en-GB': 'English (UK)',
            'ru-RU': 'Russian',
            'es-ES': 'Spanish',
            'fr-FR': 'French',
            'de-DE': 'German',
            'it-IT': 'Italian',
            'pt-PT': 'Portuguese',
            'zh-CN': 'Chinese (Simplified)',
            'ja-JP': 'Japanese',
            'ko-KR': 'Korean'
        }
    
    def test_recognition_engines(self) -> Dict[str, bool]:
        """
        Тестирование доступности движков распознавания
        
        Returns:
            dict: статус доступности каждого движка
        """
        engines = {}
        
        # Тест Google Speech Recognition
        try:
            # Создаем тестовое аудио (тишину)
            import wave
            import struct
            
            test_path = self.config.get_temp_filename("test_audio", ".wav")
            
            with wave.open(str(test_path), 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                # Запись 1 секунды тишины
                for _ in range(16000):
                    wav_file.writeframes(struct.pack('<h', 0))
            
            # Попытка распознавания
            with sr.AudioFile(str(test_path)) as source:
                audio_data = self.recognizer.record(source)
                try:
                    self.recognizer.recognize_google(audio_data, language='en-US')
                    engines['google'] = True
                except:
                    engines['google'] = False
            
            # Очистка тестового файла
            if Path(test_path).exists():
                Path(test_path).unlink()
                
        except Exception:
            engines['google'] = False
        
        # Тест Whisper
        try:
            import whisper
            engines['whisper'] = True
        except ImportError:
            engines['whisper'] = False
        
        # Тест PocketSphinx
        try:
            test_recognizer = sr.Recognizer()
            test_recognizer.recognize_sphinx(sr.AudioData(b'', 16000, 2), language='en-US')
            engines['sphinx'] = True
        except:
            engines['sphinx'] = False
        
        # Тест Vosk
        try:
            import vosk
            model_path = getattr(self.config, 'VOSK_MODEL_PATH', None)
            engines['vosk'] = bool(model_path and Path(model_path).exists())
        except ImportError:
            engines['vosk'] = False
        
        return engines


if __name__ == "__main__":
    # Тестирование модуля
    print("=== Тестирование SpeechRecognizer ===")
    
    recognizer = SpeechRecognizer()
    print("SpeechRecognizer инициализирован")
    
    # Тест доступных движков
    engines = recognizer.test_recognition_engines()
    print(f"Доступные движки распознавания: {engines}")
    
    # Тест поддерживаемых языков
    languages = recognizer.get_supported_languages()
    print(f"Поддерживаемые языки: {list(languages.keys())}")
    
    # Тест с реальным файлом
    test_file = "test.wav"
    if Path(test_file).exists():
        result = recognizer.transcribe_audio(test_file)
        print(f"Распознавание тестового файла: '{result}'")
    else:
        print(f"Тестовый файл {test_file} не найден")