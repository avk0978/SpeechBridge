#!/usr/bin/env python3
"""
VideoTranslator: Основной класс для перевода видео
Переводчик видео с английского на русский
"""

import uuid
import logging
from typing import Optional, Dict, List, Callable
from pathlib import Path

# Обработка видео и аудио
from moviepy.editor import VideoFileClip, AudioFileClip
from pydub import AudioSegment
from pydub.silence import split_on_silence

# API для распознавания, перевода и синтеза
import speech_recognition as sr
from translator_compat import translate_text, get_translator_status
from gtts import gTTS

# Локальные модули
from config import config


class VideoTranslator:
    """Основной класс для перевода видео"""

    def __init__(self):
        self.config = config
        self.setup_logging()
        self.recognizer = sr.Recognizer()
        
        # Создание рабочих директорий
        self.config.create_directories()
        
        self.logger.info("VideoTranslator инициализирован")
        self.logger.info(f"Настройки: {self.config.get_processing_config()}")

    def setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=getattr(logging, self.config.LOG_LEVEL),
            format=self.config.LOG_FORMAT,
            handlers=[
                logging.FileHandler(self.config.LOG_FILE),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def extract_audio(self, video_path: str) -> Optional[str]:
        """Извлечение аудио из видео"""
        try:
            self.logger.info(f"Извлечение аудио из {video_path}")

            # Загрузка видео
            video = VideoFileClip(video_path)
            audio = video.audio

            # Временный файл для аудио
            temp_audio_path = self.config.get_temp_filename("audio", ".wav")

            # Сохранение аудио в формате WAV для лучшей совместимости
            audio.write_audiofile(
                str(temp_audio_path),
                codec='pcm_s16le',
                ffmpeg_params=['-ac', str(self.config.AUDIO_CHANNELS), 
                             '-ar', str(self.config.AUDIO_SAMPLE_RATE)]
            )

            # Закрытие объектов для освобождения памяти
            audio.close()
            video.close()

            self.logger.info(f"Аудио извлечено: {temp_audio_path}")
            return str(temp_audio_path)

        except Exception as e:
            self.logger.error(f"Ошибка извлечения аудио: {e}")
            return None

    def segment_audio(self, audio_path: str) -> List[Dict]:
        """Сегментация аудио по паузам"""
        try:
            self.logger.info(f"Сегментация аудио: {audio_path}")

            # Загрузка аудио
            audio = AudioSegment.from_wav(audio_path)

            # Разделение по паузам с настройками из конфига
            chunks = split_on_silence(
                audio,
                min_silence_len=self.config.MIN_SILENCE_LEN,
                silence_thresh=self.config.SILENCE_THRESH,
                keep_silence=self.config.KEEP_SILENCE
            )

            segments = []
            current_time = 0

            for i, chunk in enumerate(chunks):
                if len(chunk) > 100:  # Игнорируем очень короткие фрагменты
                    # Сохранение сегмента
                    segment_path = self.config.get_temp_filename(f"segment_{i}", ".wav")
                    chunk.export(str(segment_path), format="wav")

                    segments.append({
                        'id': i,
                        'path': str(segment_path),
                        'start_time': current_time / 1000.0,
                        'end_time': (current_time + len(chunk)) / 1000.0,
                        'duration': len(chunk) / 1000.0
                    })

                current_time += len(chunk)

            self.logger.info(f"Создано {len(segments)} сегментов")
            return segments

        except Exception as e:
            self.logger.error(f"Ошибка сегментации аудио: {e}")
            return []

    def transcribe_segment(self, segment_path: str, language: str = None) -> str:
        """Распознавание речи в сегменте"""
        if language is None:
            language = self.config.SPEECH_LANGUAGE
            
        try:
            with sr.AudioFile(segment_path) as source:
                # Настройка распознавателя
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_data = self.recognizer.record(source)

                # Распознавание через Google Speech Recognition
                text = self.recognizer.recognize_google(audio_data, language=language)
                return text.strip()

        except sr.UnknownValueError:
            self.logger.debug(f"Речь не распознана в сегменте: {segment_path}")
            return ""
        except sr.RequestError as e:
            self.logger.error(f"Ошибка API распознавания речи: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Ошибка распознавания сегмента: {e}")
            return ""

    def translate_text(self, text: str, src_lang: str = None, dest_lang: str = None) -> str:
        """Перевод текста через универсальный переводчик"""
        if src_lang is None:
            src_lang = self.config.SOURCE_LANGUAGE
        if dest_lang is None:
            dest_lang = self.config.TARGET_LANGUAGE
            
        try:
            result = translate_text(text, src_lang, dest_lang)
            self.logger.debug(f"Переведено: {text[:50]}... -> {result[:50]}...")
            return result
        except Exception as e:
            self.logger.error(f"Ошибка перевода: {e}")
            return text

    def synthesize_speech(self, text: str, lang: str = None, slow: bool = False) -> Optional[str]:
        """Синтез речи из текста"""
        if lang is None:
            lang = self.config.TTS_LANGUAGE
            
        try:
            if not text.strip():
                return None

            # Создание TTS объекта
            tts = gTTS(text=text, lang=lang, slow=slow)

            # Временный файл для синтезированной речи
            temp_tts_path = self.config.get_temp_filename("tts", ".mp3")
            tts.save(str(temp_tts_path))

            return str(temp_tts_path)

        except Exception as e:
            self.logger.error(f"Ошибка синтеза речи: {e}")
            return None

    def adjust_audio_duration(self, audio_path: str, target_duration: float) -> str:
        """Подгонка длительности аудио под целевую"""
        try:
            audio = AudioSegment.from_file(audio_path)
            current_duration = len(audio) / 1000.0

            if abs(current_duration - target_duration) < 0.1:
                return audio_path  # Длительность уже подходит

            if current_duration > target_duration:
                # Ускоряем аудио
                speed_factor = current_duration / target_duration
                # Ограничиваем ускорение до разумных пределов
                speed_factor = min(speed_factor, 1.5)
                adjusted_audio = audio.speedup(playback_speed=speed_factor)
            else:
                # Добавляем тишину в конец
                silence_duration = int((target_duration - current_duration) * 1000)
                silence = AudioSegment.silent(duration=silence_duration)
                adjusted_audio = audio + silence

            # Сохранение подогнанного аудио
            adjusted_path = self.config.get_temp_filename("adjusted", ".wav")
            adjusted_audio.export(str(adjusted_path), format="wav")

            return str(adjusted_path)

        except Exception as e:
            self.logger.error(f"Ошибка подгонки длительности аудио: {e}")
            return audio_path

    def create_final_video(self, original_video_path: str, translated_audio_segments: List[Dict],
                           output_path: str) -> bool:
        """Создание финального видео с переведенным аудио"""
        try:
            self.logger.info("Создание финального видео...")

            # Загрузка оригинального видео
            video = VideoFileClip(original_video_path)

            # Объединение всех переведенных аудио сегментов
            combined_audio = AudioSegment.empty()

            for segment in translated_audio_segments:
                if segment.get('translated_audio_path'):
                    segment_audio = AudioSegment.from_file(segment['translated_audio_path'])
                    combined_audio += segment_audio
                else:
                    # Добавляем тишину если сегмент не переведен
                    silence_duration = int(segment['duration'] * 1000)
                    combined_audio += AudioSegment.silent(duration=silence_duration)

            # Сохранение объединенного аудио
            temp_combined_path = self.config.get_temp_filename("combined", ".wav")
            combined_audio.export(str(temp_combined_path), format="wav")

            # Загрузка нового аудио
            new_audio = AudioFileClip(str(temp_combined_path))

            # Подгонка длительности аудио под видео
            if new_audio.duration > video.duration:
                new_audio = new_audio.subclip(0, video.duration)
            elif new_audio.duration < video.duration:
                # Добавление тишины в конец
                silence_duration = video.duration - new_audio.duration
                silence_audio = AudioSegment.silent(duration=int(silence_duration * 1000))
                silence_path = self.config.get_temp_filename("silence", ".wav")
                silence_audio.export(str(silence_path), format="wav")

                silence_clip = AudioFileClip(str(silence_path))
                from moviepy.editor import concatenate_audioclips
                new_audio = concatenate_audioclips([new_audio, silence_clip])

            # Создание финального видео с настройками из конфига
            final_video = video.set_audio(new_audio)
            final_video.write_videofile(
                output_path,
                codec=self.config.VIDEO_CODEC,
                audio_codec=self.config.AUDIO_CODEC,
                temp_audiofile=str(self.config.get_temp_filename("temp_audio", ".m4a")),
                remove_temp=True
            )

            # Закрытие объектов
            video.close()
            new_audio.close()
            final_video.close()

            self.logger.info(f"Финальное видео создано: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка создания финального видео: {e}")
            return False

    def translate_video(self, video_path: str, output_path: str, progress_callback: Callable = None) -> bool:
        """Основная функция перевода видео"""
        try:
            self.logger.info(f"Начало перевода видео: {video_path}")

            # Обновление прогресса
            if progress_callback:
                progress_callback("Извлечение аудио из видео", 10)

            # 1. Извлечение аудио
            audio_path = self.extract_audio(video_path)
            if not audio_path:
                if progress_callback:
                    progress_callback("Ошибка извлечения аудио", 0)
                return False

            if progress_callback:
                progress_callback("Сегментация аудио", 20)

            # 2. Сегментация аудио
            segments = self.segment_audio(audio_path)
            if not segments:
                if progress_callback:
                    progress_callback("Ошибка сегментации аудио", 0)
                return False

            # 3. Обработка каждого сегмента
            translated_segments = []
            total_segments = len(segments)

            for i, segment in enumerate(segments):
                try:
                    # Обновление прогресса
                    progress = 20 + (i / total_segments) * 60
                    if progress_callback:
                        progress_callback(f"Обработка сегмента {i + 1}/{total_segments}", int(progress))

                    self.logger.info(f"Обработка сегмента {i + 1}/{total_segments}")

                    # Распознавание речи
                    original_text = self.transcribe_segment(segment['path'])
                    if not original_text:
                        self.logger.warning(f"Сегмент {i + 1}: речь не распознана")
                        translated_segments.append({
                            **segment,
                            'original_text': '',
                            'translated_text': '',
                            'translated_audio_path': None
                        })
                        continue

                    self.logger.info(f"Сегмент {i + 1} распознан: {original_text[:100]}...")

                    # Перевод текста
                    translated_text = self.translate_text(original_text)
                    self.logger.info(f"Сегмент {i + 1} переведен: {translated_text[:100]}...")

                    # Синтез речи
                    tts_path = self.synthesize_speech(translated_text)
                    if tts_path:
                        # Подгонка длительности
                        adjusted_tts_path = self.adjust_audio_duration(tts_path, segment['duration'])
                        tts_path = adjusted_tts_path

                    translated_segments.append({
                        **segment,
                        'original_text': original_text,
                        'translated_text': translated_text,
                        'translated_audio_path': tts_path
                    })

                except Exception as e:
                    self.logger.error(f"Ошибка обработки сегмента {i + 1}: {e}")
                    translated_segments.append({
                        **segment,
                        'original_text': '',
                        'translated_text': '',
                        'translated_audio_path': None
                    })

            if progress_callback:
                progress_callback("Создание финального видео", 85)

            # 4. Создание финального видео
            success = self.create_final_video(video_path, translated_segments, output_path)

            if progress_callback:
                progress_callback("Завершено" if success else "Ошибка", 100 if success else 0)

            # 5. Очистка временных файлов
            self.cleanup_temp_files([audio_path] + [seg['path'] for seg in segments] +
                                    [seg.get('translated_audio_path') for seg in translated_segments if
                                     seg.get('translated_audio_path')])

            self.logger.info(f"Перевод видео завершен: {'успешно' if success else 'с ошибкой'}")
            return success

        except Exception as e:
            self.logger.error(f"Критическая ошибка перевода видео: {e}")
            if progress_callback:
                progress_callback("Критическая ошибка", 0)
            return False

    def cleanup_temp_files(self, file_list: List[str]):
        """Очистка временных файлов"""
        for file_path in file_list:
            try:
                if file_path and Path(file_path).exists():
                    Path(file_path).unlink()
                    self.logger.debug(f"Удален временный файл: {file_path}")
            except Exception as e:
                self.logger.warning(f"Не удалось удалить временный файл {file_path}: {e}")

    def get_translator_status(self) -> Dict:
        """Получение статуса переводчика"""
        return get_translator_status()

    def validate_video_file(self, file_path: str) -> Dict[str, any]:
        """Валидация видео файла"""
        result = {
            'valid': False,
            'errors': [],
            'info': {}
        }
        
        try:
            file_path = Path(file_path)
            
            # Проверка существования файла
            if not file_path.exists():
                result['errors'].append("Файл не найден")
                return result
            
            # Проверка расширения
            if not self.config.is_allowed_file(file_path.name):
                result['errors'].append(f"Неподдерживаемый формат: {file_path.suffix}")
                return result
            
            # Проверка размера
            file_size = file_path.stat().st_size
            if not self.config.validate_file_size(file_size):
                max_size_mb = self.config.MAX_FILE_SIZE_MB
                current_size_mb = file_size / (1024 * 1024)
                result['errors'].append(f"Файл слишком большой: {current_size_mb:.1f}MB (макс. {max_size_mb}MB)")
                return result
            
            # Проверка видео с помощью moviepy
            try:
                video = VideoFileClip(str(file_path))
                duration_minutes = video.duration / 60
                
                result['info'] = {
                    'duration': video.duration,
                    'duration_minutes': duration_minutes,
                    'fps': video.fps,
                    'size': (video.w, video.h),
                    'file_size_mb': file_size / (1024 * 1024),
                    'has_audio': video.audio is not None
                }
                
                video.close()
                
                # Проверка длительности
                if duration_minutes > self.config.MAX_DURATION_MINUTES:
                    result['errors'].append(f"Видео слишком длинное: {duration_minutes:.1f} мин (макс. {self.config.MAX_DURATION_MINUTES} мин)")
                    return result
                
                # Проверка наличия аудио
                if not result['info']['has_audio']:
                    result['errors'].append("В видео отсутствует аудиодорожка")
                    return result
                
                result['valid'] = True
                
            except Exception as e:
                result['errors'].append(f"Ошибка анализа видео: {str(e)}")
                return result
        
        except Exception as e:
            result['errors'].append(f"Ошибка валидации: {str(e)}")
            
        return result


if __name__ == "__main__":
    # Тестирование класса
    print("=== Тестирование VideoTranslator ===")
    
    translator = VideoTranslator()
    print("VideoTranslator инициализирован")
    
    # Проверка статуса переводчика
    status = translator.get_translator_status()
    print(f"Статус переводчика: {status}")
    
    # Тест валидации файла (если есть тестовый файл)
    test_file = "test.mp4"
    if Path(test_file).exists():
        validation = translator.validate_video_file(test_file)
        print(f"Валидация {test_file}: {validation}")
    
    print("Тестирование завершено")
