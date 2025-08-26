#!/usr/bin/env python3
"""
VideoProcessor: Модуль обработки видео файлов
Извлечение аудио, создание финального видео с переведенной аудиодорожкой
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict

from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips
from pydub import AudioSegment

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import config


class VideoProcessor:
    """Класс для обработки видео файлов"""
    
    def __init__(self):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def extract_audio(self, video_path: str) -> Optional[str]:
        """
        Извлечение аудиодорожки из видео файла
        
        Args:
            video_path: путь к видео файлу
            
        Returns:
            str: путь к извлеченному аудио файлу или None при ошибке
        """
        try:
            self.logger.info(f"Извлечение аудио из {video_path}")
            
            # Проверка существования файла
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Видео файл не найден: {video_path}")
            
            # Загрузка видео
            video = VideoFileClip(video_path)
            
            # Проверка наличия аудио
            if video.audio is None:
                raise ValueError("В видео отсутствует аудиодорожка")
            
            audio = video.audio
            
            # Создание временного файла для аудио
            temp_audio_path = self.config.get_temp_filename("audio", ".wav")
            
            # Сохранение аудио в формате WAV
            audio.write_audiofile(
                str(temp_audio_path),
                codec='pcm_s16le',
                ffmpeg_params=[
                    '-ac', str(self.config.AUDIO_CHANNELS),
                    '-ar', str(self.config.AUDIO_SAMPLE_RATE)
                ],
                verbose=False,
                logger=None
            )
            
            # Освобождение ресурсов
            audio.close()
            video.close()
            
            self.logger.info(f"Аудио успешно извлечено: {temp_audio_path}")
            return str(temp_audio_path)
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения аудио: {e}")
            return None
    
    def create_final_video(
        self, 
        original_video_path: str, 
        translated_audio_segments: List[Dict], 
        output_path: str
    ) -> bool:
        """
        Создание финального видео с переведенным аудио
        
        Args:
            original_video_path: путь к оригинальному видео
            translated_audio_segments: список сегментов с переведенным аудио
            output_path: путь для сохранения результата
            
        Returns:
            bool: True при успехе, False при ошибке
        """
        try:
            self.logger.info("Создание финального видео с переведенным аудио...")
            
            # Проверка входных данных
            if not Path(original_video_path).exists():
                raise FileNotFoundError(f"Оригинальное видео не найдено: {original_video_path}")
            
            if not translated_audio_segments:
                raise ValueError("Нет сегментов для обработки")
            
            # Загрузка оригинального видео
            video = VideoFileClip(original_video_path)
            original_duration = video.duration
            
            # Объединение переведенных аудио сегментов
            combined_audio_path = self._combine_audio_segments(translated_audio_segments)
            
            if not combined_audio_path:
                raise RuntimeError("Не удалось объединить аудио сегменты")
            
            # Загрузка объединенного аудио
            new_audio = AudioFileClip(combined_audio_path)
            
            # Синхронизация длительности аудио с видео
            synchronized_audio = self._synchronize_audio_duration(new_audio, original_duration)
            
            # Создание финального видео
            final_video = video.set_audio(synchronized_audio)
            
            # Создание выходной директории если не существует
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Сохранение видео с настройками из конфигурации
            final_video.write_videofile(
                output_path,
                codec=self.config.VIDEO_CODEC,
                audio_codec=self.config.AUDIO_CODEC,
                temp_audiofile=str(self.config.get_temp_filename("temp_audio", ".m4a")),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # Освобождение ресурсов
            video.close()
            new_audio.close()
            synchronized_audio.close()
            final_video.close()
            
            # Очистка временных файлов
            if Path(combined_audio_path).exists():
                Path(combined_audio_path).unlink()
            
            self.logger.info(f"Финальное видео создано: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка создания финального видео: {e}")
            return False
    
    def _combine_audio_segments(self, translated_segments: List[Dict]) -> Optional[str]:
        """
        Объединение аудио сегментов в один файл
        
        Args:
            translated_segments: список сегментов с аудио
            
        Returns:
            str: путь к объединенному аудио файлу
        """
        try:
            combined_audio = AudioSegment.empty()
            
            for segment in translated_segments:
                if segment.get('translated_audio_path') and Path(segment['translated_audio_path']).exists():
                    # Добавляем переведенный аудио сегмент
                    segment_audio = AudioSegment.from_file(segment['translated_audio_path'])
                    combined_audio += segment_audio
                else:
                    # Добавляем тишину если сегмент не переведен
                    silence_duration = int(segment.get('duration', 1.0) * 1000)
                    silence = AudioSegment.silent(duration=silence_duration)
                    combined_audio += silence
            
            # Сохранение объединенного аудио
            temp_combined_path = self.config.get_temp_filename("combined", ".wav")
            combined_audio.export(str(temp_combined_path), format="wav")
            
            self.logger.debug(f"Объединено {len(translated_segments)} аудио сегментов")
            return str(temp_combined_path)
            
        except Exception as e:
            self.logger.error(f"Ошибка объединения аудио сегментов: {e}")
            return None
    
    def _synchronize_audio_duration(self, audio_clip: AudioFileClip, target_duration: float) -> AudioFileClip:
        """
        Синхронизация длительности аудио с видео
        
        Args:
            audio_clip: аудио клип
            target_duration: целевая длительность в секундах
            
        Returns:
            AudioFileClip: синхронизированный аудио клип
        """
        try:
            current_duration = audio_clip.duration
            
            if abs(current_duration - target_duration) < 0.1:
                # Длительность уже подходящая
                return audio_clip
            
            if current_duration > target_duration:
                # Обрезаем аудио до нужной длины
                self.logger.debug(f"Обрезка аудио с {current_duration:.2f}s до {target_duration:.2f}s")
                return audio_clip.subclip(0, target_duration)
            
            else:
                # Добавляем тишину в конец
                silence_duration = target_duration - current_duration
                self.logger.debug(f"Добавление {silence_duration:.2f}s тишины к аудио")
                
                # Создаем тишину как аудио файл
                silence_audio = AudioSegment.silent(duration=int(silence_duration * 1000))
                silence_path = self.config.get_temp_filename("silence", ".wav")
                silence_audio.export(str(silence_path), format="wav")
                
                silence_clip = AudioFileClip(str(silence_path))
                
                # Объединяем оригинальное аудио с тишиной
                return concatenate_audioclips([audio_clip, silence_clip])
                
        except Exception as e:
            self.logger.error(f"Ошибка синхронизации длительности аудио: {e}")
            return audio_clip
    
    def get_video_info(self, video_path: str) -> Optional[Dict]:
        """
        Получение информации о видео файле
        
        Args:
            video_path: путь к видео файлу
            
        Returns:
            dict: информация о видео или None при ошибке
        """
        try:
            if not Path(video_path).exists():
                return None
            
            video = VideoFileClip(video_path)
            
            info = {
                'duration': video.duration,
                'duration_minutes': video.duration / 60,
                'fps': video.fps,
                'size': (video.w, video.h),
                'has_audio': video.audio is not None,
                'file_size': Path(video_path).stat().st_size,
                'file_size_mb': Path(video_path).stat().st_size / (1024 * 1024)
            }
            
            video.close()
            return info
            
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о видео: {e}")
            return None
    
    def validate_video_file(self, video_path: str) -> Dict[str, any]:
        """
        Валидация видео файла
        
        Args:
            video_path: путь к видео файлу
            
        Returns:
            dict: результат валидации с информацией об ошибках
        """
        result = {
            'valid': False,
            'errors': [],
            'info': {}
        }
        
        try:
            file_path = Path(video_path)
            
            # Проверка существования файла
            if not file_path.exists():
                result['errors'].append("Файл не найден")
                return result
            
            # Проверка расширения
            if not self.config.is_allowed_file(file_path.name):
                result['errors'].append(f"Неподдерживаемый формат: {file_path.suffix}")
                return result
            
            # Проверка размера файла
            file_size = file_path.stat().st_size
            if not self.config.validate_file_size(file_size):
                max_size_mb = self.config.MAX_FILE_SIZE_MB
                current_size_mb = file_size / (1024 * 1024)
                result['errors'].append(f"Файл слишком большой: {current_size_mb:.1f}MB (макс. {max_size_mb}MB)")
                return result
            
            # Получение информации о видео
            video_info = self.get_video_info(video_path)
            if not video_info:
                result['errors'].append("Не удалось проанализировать видео файл")
                return result
            
            result['info'] = video_info
            
            # Проверка длительности
            duration_minutes = video_info['duration_minutes']
            if duration_minutes > self.config.MAX_DURATION_MINUTES:
                result['errors'].append(
                    f"Видео слишком длинное: {duration_minutes:.1f} мин "
                    f"(макс. {self.config.MAX_DURATION_MINUTES} мин)"
                )
                return result
            
            # Проверка наличия аудио
            if not video_info['has_audio']:
                result['errors'].append("В видео отсутствует аудиодорожка")
                return result
            
            result['valid'] = True
            
        except Exception as e:
            result['errors'].append(f"Ошибка валидации: {str(e)}")
        
        return result


if __name__ == "__main__":
    # Тестирование модуля
    print("=== Тестирование VideoProcessor ===")
    
    processor = VideoProcessor()
    print(f"VideoProcessor инициализирован")
    
    # Тест с фиктивным файлом
    test_file = "test.mp4"
    validation = processor.validate_video_file(test_file)
    print(f"Валидация {test_file}: {validation}")
