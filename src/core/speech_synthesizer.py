#!/usr/bin/env python3
"""
SpeechSynthesizer: Модуль синтеза речи
Поддерживает Google TTS, ElevenLabs и локальные TTS движки
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List

from gtts import gTTS

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import config


class SpeechSynthesizer:
    """Класс для синтеза речи из текста"""
    
    def __init__(self):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Настройки по умолчанию
        self.default_language = self.config.TTS_LANGUAGE
        self.default_voice = self.config.TTS_VOICE
        
        self.logger.debug("SpeechSynthesizer инициализирован")
    
    def synthesize_speech(
        self, 
        text: str, 
        language: str = None, 
        voice: str = None, 
        speed: float = 1.0,
        pitch: float = 0.0
    ) -> Optional[str]:
        """
        Синтез речи из текста с fallback стратегией
        
        Args:
            text: текст для синтеза
            language: код языка
            voice: голос для синтеза
            speed: скорость речи (0.5 - 2.0)
            pitch: высота тона (-20.0 - 20.0)
            
        Returns:
            str: путь к аудио файлу или None при ошибке
        """
        if not text or not text.strip():
            self.logger.debug("Пустой текст для синтеза")
            return None
        
        language = language or self.default_language
        voice = voice or self.default_voice
        
        try:
            self.logger.debug(f"Синтез речи: '{text[:50]}...' (lang={language}, voice={voice})")
            
            # Попытка синтеза через ElevenLabs (высокое качество)
            result = self._synthesize_with_elevenlabs(text, voice, speed)
            if result:
                self.logger.debug("ElevenLabs TTS успешно")
                return result
            
            # Fallback на Google TTS
            result = self._synthesize_with_google_tts(text, language, speed < 1.0)
            if result:
                self.logger.debug("Google TTS успешно")
                return result
            
            # Fallback на локальные TTS движки
            result = self._synthesize_with_local_tts(text, language, speed, pitch)
            if result:
                self.logger.debug("Локальный TTS успешно")
                return result
            
            self.logger.warning("Все методы синтеза речи неудачны")
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка синтеза речи: {e}")
            return None
    
    def _synthesize_with_elevenlabs(
        self, 
        text: str, 
        voice_id: str = None, 
        speed: float = 1.0
    ) -> Optional[str]:
        """
        Синтез речи через ElevenLabs API
        
        Args:
            text: текст для синтеза
            voice_id: ID голоса ElevenLabs
            speed: скорость речи
            
        Returns:
            str: путь к аудио файлу или None при ошибке
        """
        try:
            api_key = self.config.ELEVENLABS_API_KEY
            
            if not api_key or api_key == "your_elevenlabs_api_key":
                return None
            
            import requests
            import json
            
            # Настройка голоса по умолчанию
            if not voice_id:
                voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                output_path = self.config.get_temp_filename("elevenlabs_tts", ".mp3")
                
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                self.logger.debug(f"ElevenLabs TTS сохранен: {output_path}")
                return str(output_path)
            else:
                self.logger.warning(f"ElevenLabs API ошибка: {response.status_code}")
                return None
                
        except ImportError:
            self.logger.debug("requests не установлен для ElevenLabs")
            return None
        except Exception as e:
            self.logger.warning(f"ElevenLabs TTS ошибка: {e}")
            return None
    
    def _synthesize_with_google_tts(
        self, 
        text: str, 
        language: str, 
        slow: bool = False
    ) -> Optional[str]:
        """
        Синтез речи через Google Text-to-Speech
        
        Args:
            text: текст для синтеза
            language: код языка
            slow: медленная речь
            
        Returns:
            str: путь к аудио файлу или None при ошибке
        """
        try:
            # Создание объекта gTTS
            tts = gTTS(text=text, lang=language, slow=slow)
            
            # Сохранение в временный файл
            output_path = self.config.get_temp_filename("google_tts", ".mp3")
            tts.save(str(output_path))
            
            self.logger.debug(f"Google TTS сохранен: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.warning(f"Google TTS ошибка: {e}")
            return None
    
    def _synthesize_with_local_tts(
        self, 
        text: str, 
        language: str, 
        speed: float, 
        pitch: float
    ) -> Optional[str]:
        """
        Синтез речи с локальными TTS движками
        
        Args:
            text: текст для синтеза
            language: код языка
            speed: скорость речи
            pitch: высота тона
            
        Returns:
            str: путь к аудио файлу или None при ошибке
        """
        # Попытка использования разных локальных движков
        methods = [
            self._try_pyttsx3,
            self._try_espeak,
            self._try_festival,
        ]
        
        for method in methods:
            try:
                result = method(text, language, speed, pitch)
                if result:
                    return result
            except Exception as e:
                self.logger.debug(f"Локальный TTS метод неудачен: {e}")
                continue
        
        return None
    
    def _try_pyttsx3(self, text: str, language: str, speed: float, pitch: float) -> Optional[str]:
        """Попытка синтеза через pyttsx3"""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            # Настройка параметров
            voices = engine.getProperty('voices')
            
            # Поиск подходящего голоса для языка
            target_voice = None
            for voice in voices:
                if language.startswith('ru') and ('ru' in voice.id.lower() or 'russian' in voice.name.lower()):
                    target_voice = voice.id
                    break
                elif language.startswith('en') and ('en' in voice.id.lower() or 'english' in voice.name.lower()):
                    target_voice = voice.id
                    break
            
            if target_voice:
                engine.setProperty('voice', target_voice)
            
            # Настройка скорости (обычно 150-250 слов в минуту)
            rate = int(200 * speed)
            engine.setProperty('rate', rate)
            
            # Настройка громкости
            engine.setProperty('volume', 1.0)
            
            # Сохранение в файл
            output_path = self.config.get_temp_filename("pyttsx3_tts", ".wav")
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            
            if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                return str(output_path)
            
            return None
            
        except ImportError:
            return None
        except Exception:
            return None
    
    def _try_espeak(self, text: str, language: str, speed: float, pitch: float) -> Optional[str]:
        """Попытка синтеза через eSpeak"""
        try:
            import subprocess
            
            # Проверка наличия eSpeak
            subprocess.run(['espeak', '--version'], 
                          capture_output=True, check=True)
            
            output_path = self.config.get_temp_filename("espeak_tts", ".wav")
            
            # Настройка параметров
            lang_code = 'ru' if language.startswith('ru') else 'en'
            speed_wpm = int(175 * speed)  # слов в минуту
            pitch_val = int(50 + pitch)   # 0-99
            
            cmd = [
                'espeak',
                '-v', lang_code,
                '-s', str(speed_wpm),
                '-p', str(pitch_val),
                '-w', str(output_path),
                text
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and Path(output_path).exists():
                return str(output_path)
            
            return None
            
        except (ImportError, subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def _try_festival(self, text: str, language: str, speed: float, pitch: float) -> Optional[str]:
        """Попытка синтеза через Festival"""
        try:
            import subprocess
            
            # Проверка наличия Festival
            subprocess.run(['festival', '--version'], 
                          capture_output=True, check=True)
            
            output_path = self.config.get_temp_filename("festival_tts", ".wav")
            
            # Создание временного текстового файла
            text_path = self.config.get_temp_filename("festival_text", ".txt")
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Команда Festival
            cmd = [
                'festival',
                '--tts',
                str(text_path)
            ]
            
            # Перенаправление вывода в WAV файл
            with open(output_path, 'wb') as output_file:
                result = subprocess.run(cmd, stdout=output_file, stderr=subprocess.PIPE)
            
            # Очистка временного файла
            Path(text_path).unlink(missing_ok=True)
            
            if result.returncode == 0 and Path(output_path).exists():
                return str(output_path)
            
            return None
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def synthesize_batch(
        self, 
        texts: List[str], 
        language: str = None, 
        voice: str = None
    ) -> List[Dict]:
        """
        Пакетный синтез речи для нескольких текстов
        
        Args:
            texts: список текстов для синтеза
            language: код языка
            voice: голос для синтеза
            
        Returns:
            list: список результатов синтеза
        """
        results = []
        
        for i, text in enumerate(texts):
            self.logger.info(f"Синтез текста {i+1}/{len(texts)}: '{text[:30]}...'")
            
            start_time = None
            try:
                import time
                start_time = time.time()
                
                audio_path = self.synthesize_speech(text, language, voice)
                
                processing_time = time.time() - start_time if start_time else 0
                
                result = {
                    'text': text,
                    'audio_path': audio_path,
                    'success': bool(audio_path),
                    'processing_time': processing_time,
                    'error': None
                }
                
            except Exception as e:
                result = {
                    'text': text,
                    'audio_path': None,
                    'success': False,
                    'processing_time': 0,
                    'error': str(e)
                }
                
                self.logger.error(f"Ошибка синтеза текста '{text[:30]}...': {e}")
            
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(f"Пакетный синтез завершен: {success_count}/{len(texts)} успешно")
        
        return results
    
    def get_available_voices(self) -> Dict[str, List[Dict]]:
        """
        Получение списка доступных голосов
        
        Returns:
            dict: словарь с голосами по языкам
        """
        voices = {
            'google_tts': [
                {'id': 'ru', 'name': 'Russian', 'language': 'ru'},
                {'id': 'en', 'name': 'English', 'language': 'en'},
                {'id': 'es', 'name': 'Spanish', 'language': 'es'},
                {'id': 'fr', 'name': 'French', 'language': 'fr'},
                {'id': 'de', 'name': 'German', 'language': 'de'},
                {'id': 'it', 'name': 'Italian', 'language': 'it'},
            ],
            'elevenlabs': [
                {'id': '21m00Tcm4TlvDq8ikWAM', 'name': 'Rachel', 'language': 'en'},
                {'id': 'AZnzlk1XvdvUeBnXmlld', 'name': 'Domi', 'language': 'en'},
                {'id': 'EXAVITQu4vr4xnSDxMaL', 'name': 'Bella', 'language': 'en'},
                # Русские голоса ElevenLabs (если доступны)
                {'id': 'custom_ru_voice', 'name': 'Russian Voice', 'language': 'ru'},
            ]
        }
        
        # Добавление локальных голосов если доступны
        try:
            import pyttsx3
            engine = pyttsx3.init()
            local_voices = engine.getProperty('voices')
            
            voices['local'] = []
            for voice in local_voices:
                voices['local'].append({
                    'id': voice.id,
                    'name': voice.name,
                    'language': self._detect_voice_language(voice.name)
                })
                
        except ImportError:
            voices['local'] = []
        
        return voices
    
    def _detect_voice_language(self, voice_name: str) -> str:
        """Определение языка голоса по имени"""
        voice_name_lower = voice_name.lower()
        
        if any(word in voice_name_lower for word in ['russian', 'ru', 'милена', 'александр']):
            return 'ru'
        elif any(word in voice_name_lower for word in ['english', 'en', 'american', 'british']):
            return 'en'
        elif any(word in voice_name_lower for word in ['spanish', 'es', 'español']):
            return 'es'
        elif any(word in voice_name_lower for word in ['french', 'fr', 'français']):
            return 'fr'
        elif any(word in voice_name_lower for word in ['german', 'de', 'deutsch']):
            return 'de'
        else:
            return 'unknown'
    
    def test_tts_engines(self) -> Dict[str, bool]:
        """
        Тестирование доступности TTS движков
        
        Returns:
            dict: статус доступности каждого движка
        """
        engines = {}
        test_text = "Hello world"
        
        # Тест Google TTS
        try:
            result = self._synthesize_with_google_tts(test_text, 'en')
            engines['google_tts'] = bool(result)
            if result and Path(result).exists():
                Path(result).unlink()  # Очистка тестового файла
        except Exception:
            engines['google_tts'] = False
        
        # Тест ElevenLabs
        try:
            result = self._synthesize_with_elevenlabs(test_text)
            engines['elevenlabs'] = bool(result)
            if result and Path(result).exists():
                Path(result).unlink()  # Очистка тестового файла
        except Exception:
            engines['elevenlabs'] = False
        
        # Тест pyttsx3
        try:
            import pyttsx3
            engines['pyttsx3'] = True
        except ImportError:
            engines['pyttsx3'] = False
        
        # Тест eSpeak
        try:
            import subprocess
            subprocess.run(['espeak', '--version'], capture_output=True, check=True)
            engines['espeak'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            engines['espeak'] = False
        
        return engines
    
    def estimate_synthesis_time(self, text: str, method: str = 'google_tts') -> float:
        """
        Оценка времени синтеза речи
        
        Args:
            text: текст для синтеза
            method: метод синтеза
            
        Returns:
            float: оценка времени в секундах
        """
        char_count = len(text)
        word_count = len(text.split())
        
        # Примерные времена для разных методов
        time_estimates = {
            'google_tts': 0.1 + (char_count * 0.01),      # ~0.01s на символ
            'elevenlabs': 0.5 + (word_count * 0.2),       # ~0.2s на слово
            'local': 0.05 + (word_count * 0.1),           # ~0.1s на слово
        }
        
        return time_estimates.get(method, char_count * 0.01)
    
    def get_synthesis_quality_info(self, audio_path: str) -> Optional[Dict]:
        """
        Анализ качества синтезированной речи
        
        Args:
            audio_path: путь к аудио файлу
            
        Returns:
            dict: информация о качестве
        """
        try:
            if not Path(audio_path).exists():
                return None
            
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            
            # Базовые характеристики качества
            quality_info = {
                'sample_rate': audio.frame_rate,
                'bit_depth': audio.sample_width * 8,
                'channels': audio.channels,
                'duration': len(audio) / 1000.0,
                'file_size': Path(audio_path).stat().st_size,
                'average_loudness': audio.dBFS,
                'max_loudness': audio.max_dBFS,
                'format': Path(audio_path).suffix[1:].upper()
            }
            
            # Оценка качества на основе параметров
            quality_score = self._calculate_quality_score(quality_info)
            quality_info['quality_score'] = quality_score
            quality_info['quality_rating'] = self._get_quality_rating(quality_score)
            
            return quality_info
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа качества: {e}")
            return None
    
    def _calculate_quality_score(self, info: Dict) -> float:
        """Расчет оценки качества на основе технических параметров"""
        score = 0.0
        
        # Sample rate (до 40 баллов)
        if info['sample_rate'] >= 44100:
            score += 40
        elif info['sample_rate'] >= 22050:
            score += 30
        elif info['sample_rate'] >= 16000:
            score += 20
        else:
            score += 10
        
        # Bit depth (до 30 баллов)
        if info['bit_depth'] >= 24:
            score += 30
        elif info['bit_depth'] >= 16:
            score += 25
        else:
            score += 15
        
        # Громкость (до 30 баллов)
        loudness = info['average_loudness']
        if -25 <= loudness <= -10:  # Оптимальный диапазон
            score += 30
        elif -35 <= loudness <= -5:
            score += 20
        else:
            score += 10
        
        return min(score, 100)  # Максимум 100 баллов
    
    def _get_quality_rating(self, score: float) -> str:
        """Преобразование оценки в текстовый рейтинг"""
        if score >= 90:
            return "Отличное"
        elif score >= 75:
            return "Хорошее"
        elif score >= 60:
            return "Удовлетворительное"
        elif score >= 40:
            return "Низкое"
        else:
            return "Очень низкое"


if __name__ == "__main__":
    # Тестирование модуля
    print("=== Тестирование SpeechSynthesizer ===")
    
    synthesizer = SpeechSynthesizer()
    print("SpeechSynthesizer инициализирован")
    
    # Тест доступных движков
    engines = synthesizer.test_tts_engines()
    print(f"Доступные TTS движки: {engines}")
    
    # Тест доступных голосов
    voices = synthesizer.get_available_voices()
    for engine, voice_list in voices.items():
        print(f"{engine}: {len(voice_list)} голосов")
    
    # Тест синтеза
    test_text = "Привет мир"
    result = synthesizer.synthesize_speech(test_text)
    if result:
        print(f"Тестовый синтез успешен: {result}")
        
        # Анализ качества
        quality = synthesizer.get_synthesis_quality_info(result)
        if quality:
            print(f"Качество: {quality['quality_rating']} ({quality['quality_score']:.1f}/100)")
    else:
        print("Тестовый синтез неудачен")