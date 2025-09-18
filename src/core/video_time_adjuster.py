#!/usr/bin/env python3
"""
Модуль для адаптивного изменения скорости видео
Позволяет притормаживать или ускорять видео для синхронизации с аудио
"""

import logging
import subprocess
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

class VideoTimeAdjuster:
    """Класс для адаптивного изменения времени видео"""
    
    def __init__(self, config=None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def adjust_video_for_audio(
        self, 
        video_path: str, 
        audio_path: str, 
        output_path: str,
        segments: List[Dict] = None
    ) -> bool:
        """
        Адаптивно изменяет скорость видео для синхронизации с аудио
        
        Args:
            video_path: путь к исходному видео
            audio_path: путь к аудио дорожке
            output_path: путь для сохранения результата
            segments: список сегментов для точной синхронизации
            
        Returns:
            bool: успешность операции
        """
        try:
            # Получаем длительности
            video_duration = self._get_media_duration(video_path)
            audio_duration = self._get_media_duration(audio_path)
            
            self.logger.info(f"🎬 Исходное видео: {video_duration:.2f}s")
            self.logger.info(f"🎵 Аудио дорожка: {audio_duration:.2f}s")
            
            # Рассчитываем коэффициент растяжения
            stretch_factor = audio_duration / video_duration if video_duration > 0 else 1.0
            
            self.logger.info(f"⚖️ Коэффициент растяжения: {stretch_factor:.3f}")
            
            if abs(stretch_factor - 1.0) < 0.02:  # Различие меньше 2%
                self.logger.info("✅ Длительности близки, используем простое объединение")
                return self._simple_combine(video_path, audio_path, output_path)
            
            elif stretch_factor > 1.0 and stretch_factor <= 1.5:  # Замедляем до 50%
                self.logger.info(f"🐌 Замедляем видео в {stretch_factor:.2f} раза")
                return self._stretch_video(video_path, audio_path, output_path, stretch_factor)
                
            elif stretch_factor < 1.0 and stretch_factor >= 0.7:  # Ускоряем до 30%
                self.logger.info(f"🏃 Ускоряем видео в {1/stretch_factor:.2f} раза")
                return self._stretch_video(video_path, audio_path, output_path, stretch_factor)
                
            else:
                # Слишком большая разница - используем сегментированный подход
                self.logger.warning(f"⚠️ Большая разница длительности ({stretch_factor:.2f}x)")
                if segments:
                    return self._segment_based_adjustment(video_path, audio_path, output_path, segments)
                else:
                    return self._adaptive_speed_adjustment(video_path, audio_path, output_path, stretch_factor)
                    
        except Exception as e:
            self.logger.error(f"❌ Ошибка адаптации видео: {e}")
            return False
    
    def _stretch_video(self, video_path: str, audio_path: str, output_path: str, factor: float) -> bool:
        """Равномерно растягивает или сжимает видео"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-filter_complex', f'[0:v]setpts={factor}*PTS[v]',
                '-map', '[v]',
                '-map', '1:a',
                '-c:a', 'aac',
                '-c:v', 'libx264',
                '-preset', 'medium',
                output_path
            ]
            
            self.logger.debug(f"🔧 FFmpeg команда: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                self.logger.info("✅ Видео адаптировано успешно")
                return True
            else:
                self.logger.error(f"❌ FFmpeg ошибка: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка растяжения видео: {e}")
            return False
    
    def _segment_based_adjustment(
        self, 
        video_path: str, 
        audio_path: str, 
        output_path: str, 
        segments: List[Dict]
    ) -> bool:
        """
        Адаптация скорости по сегментам для точной синхронизации
        """
        try:
            self.logger.info("🎭 Применяем сегментированную адаптацию скорости")
            
            # Создаем временные файлы для сегментов видео
            video_segments = []
            
            for i, segment in enumerate(segments):
                start_time = segment['start_time']
                duration = segment['duration']
                
                # Извлекаем сегмент видео
                video_segment_path = self._extract_video_segment(
                    video_path, start_time, duration, i
                )
                
                if video_segment_path:
                    video_segments.append(video_segment_path)
            
            # Объединяем сегменты с аудио
            return self._combine_video_segments_with_audio(
                video_segments, audio_path, output_path
            )
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка сегментированной адаптации: {e}")
            return False
    
    def _adaptive_speed_adjustment(
        self, 
        video_path: str, 
        audio_path: str, 
        output_path: str, 
        factor: float
    ) -> bool:
        """
        Адаптивное изменение скорости с плавными переходами
        """
        try:
            self.logger.info(f"🎛️ Применяем адаптивную коррекцию скорости (factor={factor:.2f})")
            
            if factor > 2.0:
                # Очень медленно - добавляем паузы между сегментами
                return self._add_video_pauses(video_path, audio_path, output_path, factor)
            elif factor < 0.5:
                # Очень быстро - дублируем некоторые кадры
                return self._extend_video_frames(video_path, audio_path, output_path, factor)
            else:
                # Умеренное изменение - используем setpts
                return self._stretch_video(video_path, audio_path, output_path, factor)
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка адаптивной коррекции: {e}")
            return False
    
    def _add_video_pauses(self, video_path: str, audio_path: str, output_path: str, factor: float) -> bool:
        """Добавляет паузы в видео для увеличения длительности"""
        try:
            # Рассчитываем длительность пауз
            video_duration = self._get_media_duration(video_path)
            total_pause_time = video_duration * (factor - 1.0)
            
            self.logger.info(f"⏸️ Добавляем {total_pause_time:.1f}s пауз в видео")
            
            # Создаем черный кадр для пауз
            pause_filter = f"color=black:size=1280x720:duration={total_pause_time}:rate=25[pause]"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-filter_complex', 
                f'{pause_filter};[0:v][pause]concat=n=2:v=1:a=0[v]',
                '-map', '[v]',
                '-map', '1:a',
                '-c:a', 'aac',
                '-c:v', 'libx264',
                '-preset', 'fast',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                self.logger.info("✅ Паузы добавлены успешно")
                return True
            else:
                self.logger.error(f"❌ Ошибка добавления пауз: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка добавления пауз: {e}")
            return False
    
    def _extend_video_frames(self, video_path: str, audio_path: str, output_path: str, factor: float) -> bool:
        """Расширяет видео дублированием кадров"""
        try:
            self.logger.info(f"🖼️ Расширяем видео дублированием кадров (factor={factor:.2f})")
            
            # Используем fps filter для дублирования кадров
            fps_multiplier = 1.0 / factor
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-filter_complex', f'[0:v]fps=fps=25*{fps_multiplier}[v]',
                '-map', '[v]',
                '-map', '1:a',
                '-c:a', 'aac',
                '-c:v', 'libx264',
                '-preset', 'medium',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                self.logger.info("✅ Кадры расширены успешно")
                return True
            else:
                self.logger.error(f"❌ Ошибка расширения кадров: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка расширения кадров: {e}")
            return False
    
    def _simple_combine(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """Простое объединение без изменения скорости"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.logger.info("✅ Простое объединение успешно")
                return True
            else:
                self.logger.error(f"❌ Ошибка объединения: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка простого объединения: {e}")
            return False
    
    def _get_media_duration(self, media_path: str) -> float:
        """Получает длительность медиа файла"""
        try:
            cmd = [
                'ffprobe', 
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                media_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                self.logger.warning(f"Не удалось получить длительность {media_path}")
                return 0.0
                
        except Exception as e:
            self.logger.error(f"Ошибка получения длительности {media_path}: {e}")
            return 0.0
    
    def _extract_video_segment(self, video_path: str, start_time: float, duration: float, segment_id: int) -> Optional[str]:
        """Извлекает сегмент видео"""
        try:
            if self.config:
                segment_path = self.config.get_temp_filename(f"video_segment_{segment_id}", ".mp4")
            else:
                segment_path = f"/tmp/video_segment_{segment_id}.mp4"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c', 'copy',
                segment_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                return segment_path
            else:
                self.logger.error(f"❌ Ошибка извлечения сегмента: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка извлечения сегмента видео: {e}")
            return None
    
    def _combine_video_segments_with_audio(
        self, 
        video_segments: List[str], 
        audio_path: str, 
        output_path: str
    ) -> bool:
        """Объединяет сегменты видео с аудио"""
        try:
            # Создаем список файлов для concat
            concat_file = "/tmp/video_segments_list.txt"
            
            with open(concat_file, 'w') as f:
                for segment in video_segments:
                    f.write(f"file '{segment}'\n")
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-i', audio_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'medium',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            # Очистка временных файлов
            try:
                Path(concat_file).unlink()
                for segment in video_segments:
                    Path(segment).unlink()
            except:
                pass
            
            if result.returncode == 0:
                self.logger.info("✅ Сегменты объединены успешно")
                return True
            else:
                self.logger.error(f"❌ Ошибка объединения сегментов: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка объединения сегментов: {e}")
            return False