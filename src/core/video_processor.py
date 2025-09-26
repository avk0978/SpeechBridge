#!/usr/bin/env python3
"""
VideoProcessor: Модуль обработки видео файлов
Извлечение аудио, создание финального видео с переведенной аудиодорожкой
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List

# Fix для multiprocessing и MoviePy на macOS
os.environ['IMAGEIO_FFMPEG_EXE'] = '/usr/local/bin/ffmpeg'  # Правильный путь к ffmpeg
os.environ['FFMPEG_BINARY'] = 'ffmpeg'  # Общий fallback

import moviepy.editor as mp
from pydub import AudioSegment
import uuid

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Улучшенный процессор видео с правильным сохранением аудио"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Временные файлы для отслеживания
        self.temp_files = []

    def extract_audio(self, video_path: str) -> Tuple[Optional[str], dict]:
        """
        Извлекает аудио из видео файла

        Returns:
            tuple: (путь к аудио файлу, информация о видео)
        """
        try:
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Видео файл не найден: {video_path}")

            self.logger.info(f"Извлечение аудио из {video_path}")

            # Загружаем видео
            video = mp.VideoFileClip(video_path)

            # Получаем информацию о видео
            video_info = {
                "duration": video.duration,
                "fps": video.fps,
                "size": video.size,
                "has_audio": video.audio is not None,
                "file_size": Path(video_path).stat().st_size
            }

            if not video.audio:
                self.logger.error("Видео не содержит аудио дорожку")
                video.close()
                return None, video_info

            # Создаем уникальный временный файл для аудио
            audio_filename = f"audio_{uuid.uuid4().hex}.wav"
            temp_dir = Path(__file__).parent.parent / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            audio_path = temp_dir / audio_filename

            # Извлекаем аудио в оптимальном качестве для распознавания речи
            video.audio.write_audiofile(
                str(audio_path),
                codec='pcm_s16le',  # 16-bit PCM
                ffmpeg_params=['-ac', '1', '-ar', '16000'],  # моно, 16kHz
                verbose=False,
                logger=None
            )

            # Добавляем в список для очистки
            self.temp_files.append(str(audio_path))

            video.close()
            self.logger.info(f"Аудио успешно извлечено: {audio_path}")

            return str(audio_path), video_info

        except Exception as e:
            self.logger.error(f"Ошибка извлечения аудио: {e}")
            if 'video' in locals():
                video.close()
            return None, {}

    def create_final_video(self, original_video_path: str, translated_audio_segments: List[dict],
                           output_path: str, preserve_original_audio: bool = False, 
                           adjust_video_speed: bool = True) -> bool:
        """
        Создает финальное видео с переведенной аудио дорожкой

        Args:
            original_video_path: путь к оригинальному видео
            translated_audio_segments: список сегментов с переведенным аудио
            output_path: путь для сохранения
            preserve_original_audio: сохранить оригинальное аудио как фон
            adjust_video_speed: замедлить видео по сегментам для синхронизации

        Returns:
            bool: успех операции
        """
        video = None
        final_audio_path = None

        try:
            self.logger.info("=== СОЗДАНИЕ ФИНАЛЬНОГО ВИДЕО ===")
            self.logger.info("Загрузка оригинального видео...")

            # СНАЧАЛА загружаем оригинальное видео
            video = mp.VideoFileClip(original_video_path)

            # ТЕПЕРЬ можем проводить диагностику с использованием video
            self.logger.info(f"Получено сегментов: {len(translated_audio_segments)}")
            self.logger.info(f"Длительность видео: {video.duration:.2f}s")
            
            # Корректируем скорость видео по сегментам, если включена опция
            if adjust_video_speed:
                video = self._adjust_video_speed_by_segments(video, translated_audio_segments)
                self.logger.info(f"Длительность видео после корректировки: {video.duration:.2f}s")

            # Диагностика полученных сегментов
            segments_with_audio = 0
            for i, segment in enumerate(translated_audio_segments):
                audio_path = segment.get('translated_audio_path')
                if audio_path and Path(audio_path).exists():
                    segments_with_audio += 1
                    file_size = Path(audio_path).stat().st_size
                    self.logger.info(f"Сегмент {i}: ЕСТЬ аудио файл ({file_size} байт) - {audio_path}")
                else:
                    self.logger.warning(f"Сегмент {i}: НЕТ аудио файла - {audio_path}")

            self.logger.info(f"Сегментов с аудио файлами: {segments_with_audio}/{len(translated_audio_segments)}")

            # Проверка наличия сегментов с аудио
            if not translated_audio_segments or segments_with_audio == 0:
                self.logger.warning("Нет переведенных аудио сегментов, создаем видео без звука")
                final_video = video.without_audio()
            else:
                self.logger.info("Переходим к объединению аудио сегментов...")

                # Создаем финальную аудио дорожку
                final_audio_path = self._combine_translated_audio(
                    translated_audio_segments,
                    video.duration,
                    preserve_original_audio,
                    video.audio if preserve_original_audio else None,
                    original_video_path
                )

                if final_audio_path and Path(final_audio_path).exists():
                    self.logger.info(f"✓ Переведенное аудио создано: {final_audio_path}")

                    # Проверим размер файла
                    file_size = Path(final_audio_path).stat().st_size
                    self.logger.info(f"  Размер файла: {file_size} байт")
                    #***************************************************************
                    if file_size > 1000:  # Минимум 1KB
                        # Используем FFmpeg напрямую для избежания проблем с MoviePy
                        try:
                            import subprocess

                            self.logger.info("Использование FFmpeg для объединения видео и аудио")

                            # Создаем временное видео без звука
                            temp_video_path = output_path.replace('.mp4', '_temp_silent.mp4')
                            silent_video = video.without_audio()
                            silent_video.write_videofile(
                                temp_video_path,
                                codec='libx264',
                                verbose=False,
                                logger=None
                            )
                            silent_video.close()

                            # Получаем длительности для интеллектуального объединения
                            video_duration = self._get_media_duration(temp_video_path)
                            audio_duration = self._get_media_duration(final_audio_path)
                            
                            self.logger.info(f"📊 Длительности: видео={video_duration:.2f}s, аудио={audio_duration:.2f}s")
                            
                            # Интеллектуальное объединение без потери смысла
                            cmd = [
                                'ffmpeg', '-y',
                                '-i', temp_video_path,  # видео без звука
                                '-i', final_audio_path,  # аудио дорожка
                                '-c:v', 'copy',  # копируем видео
                                '-c:a', 'aac',  # кодируем аудио в AAC
                            ]
                            
                            # ИСПРАВЛЕННАЯ ЛОГИКА: Всегда сохраняем полное аудио для избежания потери смысла
                            # Определяем реальную длительность аудио через PyDub для точности
                            try:
                                from pydub import AudioSegment
                                audio_segment = AudioSegment.from_file(final_audio_path)
                                real_audio_duration = len(audio_segment) / 1000.0
                                self.logger.info(f"🔍 РЕАЛЬНАЯ длительность аудио: {real_audio_duration:.2f}s (PyDub)")
                            except:
                                real_audio_duration = audio_duration
                                self.logger.warning("⚠️ Используем FFprobe длительность аудио")
                            
                            if real_audio_duration > video_duration + 0.5:  # Аудио заметно длиннее
                                # Расширяем видео черным кадром для сохранения всего аудио
                                # ИСПРАВЛЕНИЕ: Нельзя использовать -c:v copy с filter_complex, поэтому перекодируем
                                cmd[cmd.index('-c:v')] = '-c:v'  # Находим позицию
                                cmd[cmd.index('copy')] = 'libx264'  # Заменяем copy на libx264
                                cmd.extend(['-filter_complex', f'[0:v]tpad=stop_mode=clone:stop_duration={real_audio_duration - video_duration}[v]', '-map', '[v]', '-map', '1:a'])
                                self.logger.info("🔧 РАСШИРЯЕМ ВИДЕО: добавляем черные кадры для сохранения всего аудио")
                            elif abs(real_audio_duration - video_duration) < 0.5:
                                # Длительности действительно близки
                                self.logger.info("🔧 Длительности близки, используем стандартное объединение")
                            else:
                                # Видео длиннее - сохраняем все аудио
                                self.logger.info("🔧 Видео длиннее, но сохраняем все аудио")
                            
                            cmd.append(output_path)

                            result = subprocess.run(cmd, capture_output=True, text=True)

                            if result.returncode == 0:
                                self.logger.info("✓ Видео и аудио объединены через FFmpeg")

                                # Удаляем временный файл
                                Path(temp_video_path).unlink()

                                # Пропускаем стандартную процедуру экспорта
                                video.close()

                                # Проверяем результат
                                if Path(output_path).exists():
                                    output_size = Path(output_path).stat().st_size
                                    self.logger.info(f"✓ Финальное видео создано: {output_path}")
                                    self.logger.info(f"  Размер файла: {output_size / (1024 * 1024):.1f} MB")

                                    # Проверяем наличие аудио
                                    try:
                                        test_video = mp.VideoFileClip(output_path)
                                        has_audio = test_video.audio is not None
                                        self.logger.info(f"  Содержит аудио: {has_audio}")
                                        if has_audio:
                                            self.logger.info(f"  Длительность аудио: {test_video.audio.duration:.2f}s")
                                        test_video.close()
                                    except Exception as e:
                                        self.logger.warning(f"Не удалось проверить аудио в результате: {e}")

                                    return True
                                else:
                                    self.logger.error("Файл не создан после FFmpeg")

                            else:
                                self.logger.error(f"FFmpeg ошибка: {result.stderr}")
                                self.logger.warning("Создаем видео без звука как fallback")
                                # Переименовываем временное видео в финальное
                                Path(temp_video_path).rename(output_path)
                                video.close()
                                return True

                        except Exception as ffmpeg_error:
                            self.logger.error(f"Ошибка FFmpeg: {ffmpeg_error}")
                            self.logger.warning("Создаем видео без звука")
                            final_video = video.without_audio()

                    else:
                        self.logger.warning("Аудио файл слишком маленький, создаем без звука")
                        final_video = video.without_audio()

                    # if file_size > 1000:  # Минимум 1KB
                    #     # Загружаем переведенное аудио
                    #     translated_audio = mp.AudioFileClip(final_audio_path)
                    #
                    #
                    #     # Проверяем длительность
                    #     self.logger.info(f"  Длительность аудио: {translated_audio.duration:.2f}s")
                    #     self.logger.info(f"  Длительность видео: {video.duration:.2f}s")
                    #
                    #     # Создаем финальное видео с переведенным аудио
                    #     final_video = video.set_audio(translated_audio)
                    #     translated_audio.close()
                    #
                    #     self.logger.info("✓ Видео объединено с переведенным аудио")
                    # else:
                    #     self.logger.warning("Аудио файл слишком маленький, создаем без звука")
                    #     final_video = video.without_audio()
                else:
                    self.logger.warning("Не удалось создать переведенное аудио, создаем без звука")
                    final_video = video.without_audio()

            # Сохраняем финальное видео
            self.logger.info("Экспорт финального видео...")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                remove_temp=True,
                verbose=False,
                logger=None
            )

            # Закрываем все клипы
            final_video.close()
            video.close()

            # Проверяем результат
            if Path(output_path).exists():
                output_size = Path(output_path).stat().st_size
                self.logger.info(f"✓ Финальное видео создано: {output_path}")
                self.logger.info(f"  Размер файла: {output_size / (1024 * 1024):.1f} MB")

                # Быстрая проверка наличия аудио в результате
                try:
                    test_video = mp.VideoFileClip(output_path)
                    has_audio = test_video.audio is not None
                    self.logger.info(f"  Содержит аудио: {has_audio}")
                    if has_audio:
                        self.logger.info(f"  Длительность аудио: {test_video.audio.duration:.2f}s")
                    test_video.close()
                except Exception as e:
                    self.logger.warning(f"Не удалось проверить аудио в результате: {e}")
            else:
                self.logger.error("✗ Финальное видео не создано!")
                return False

            # Очистка временных файлов
            if final_audio_path and Path(final_audio_path).exists():
                try:
                    Path(final_audio_path).unlink()
                    self.logger.debug(f"Удален временный аудио файл: {final_audio_path}")
                except Exception as e:
                    self.logger.warning(f"Ошибка удаления временного файла: {e}")

            return True

        except Exception as e:
            self.logger.error(f"КРИТИЧЕСКАЯ ОШИБКА создания финального видео: {e}")
            import traceback
            self.logger.error(f"Трассировка:\n{traceback.format_exc()}")

            # Закрытие ресурсов в случае ошибки
            if video:
                try:
                    video.close()
                except Exception as cleanup_e:
                    self.logger.warning(f"Ошибка закрытия видео: {cleanup_e}")

            # Очистка временных файлов
            if final_audio_path and Path(final_audio_path).exists():
                try:
                    Path(final_audio_path).unlink()
                except Exception as cleanup_e:
                    self.logger.warning(f"Ошибка удаления временного файла: {cleanup_e}")

            return False
    
    def _adjust_video_speed_by_segments(self, video: mp.VideoFileClip, 
                                       translated_audio_segments: List[dict]) -> mp.VideoFileClip:
        """
        Замедляет видео по сегментам для синхронизации с переведенным аудио
        
        Args:
            video: исходное видео
            translated_audio_segments: сегменты с информацией о временных рамках
            
        Returns:
            VideoFileClip: видео с измененной скоростью
        """
        try:
            self.logger.info("=== ЗАМЕДЛЕНИЕ ВИДЕО ПО СЕГМЕНТАМ ===")
            
            # Собираем все сегменты с аудио файлами
            valid_segments = []
            for segment in translated_audio_segments:
                if (segment.get('translated_audio_path') and 
                    Path(segment['translated_audio_path']).exists() and
                    segment.get('success', False)):
                    
                    # Получаем реальную длительность переведенного аудио
                    try:
                        audio_segment = AudioSegment.from_file(segment['translated_audio_path'])
                        translated_duration = len(audio_segment) / 1000.0
                        
                        original_duration = segment.get('end_time', 0) - segment.get('start_time', 0)
                        speed_ratio = original_duration / translated_duration if translated_duration > 0 else 1.0
                        
                        valid_segments.append({
                            'start_time': segment.get('start_time', 0),
                            'end_time': segment.get('end_time', 0),
                            'original_duration': original_duration,
                            'translated_duration': translated_duration,
                            'speed_ratio': speed_ratio
                        })
                        
                        self.logger.info(f"Сегмент {segment.get('start_time', 0):.1f}-{segment.get('end_time', 0):.1f}s: "
                                       f"оригинал={original_duration:.1f}s, перевод={translated_duration:.1f}s, "
                                       f"коэффициент={speed_ratio:.2f}")
                    except Exception as e:
                        self.logger.warning(f"Ошибка анализа сегмента {segment.get('translated_audio_path')}: {e}")
                        continue
            
            if not valid_segments:
                self.logger.warning("Нет валидных сегментов для корректировки скорости")
                return video
            
            # Создаем список клипов с разными скоростями
            video_clips = []
            current_time = 0
            
            for segment in sorted(valid_segments, key=lambda x: x['start_time']):
                start_time = segment['start_time']
                end_time = segment['end_time']
                speed_ratio = segment['speed_ratio']
                
                # Добавляем промежуток до сегмента (нормальная скорость)
                if current_time < start_time:
                    normal_clip = video.subclip(current_time, start_time)
                    video_clips.append(normal_clip)
                    self.logger.debug(f"Нормальный клип: {current_time:.1f}-{start_time:.1f}s")
                
                # Добавляем сегмент с измененной скоростью
                if speed_ratio != 1.0 and speed_ratio > 0.1:  # Минимальная скорость 0.1x
                    segment_clip = video.subclip(start_time, end_time)
                    
                    # Замедляем или ускоряем видео
                    from moviepy.video.fx.speedx import speedx
                    if speed_ratio < 1.0:  # Нужно замедлить
                        adjusted_clip = segment_clip.fx(speedx, speed_ratio)
                        self.logger.info(f"Замедлен клип {start_time:.1f}-{end_time:.1f}s с коэффициентом {speed_ratio:.2f}")
                    else:  # Нужно ускорить
                        adjusted_clip = segment_clip.fx(speedx, speed_ratio)
                        self.logger.info(f"Ускорен клип {start_time:.1f}-{end_time:.1f}s с коэффициентом {speed_ratio:.2f}")
                    
                    video_clips.append(adjusted_clip)
                else:
                    # Если коэффициент некорректный, оставляем как есть
                    normal_clip = video.subclip(start_time, end_time)
                    video_clips.append(normal_clip)
                    self.logger.warning(f"Сегмент {start_time:.1f}-{end_time:.1f}s: некорректный коэффициент {speed_ratio:.2f}, оставлен без изменений")
                
                current_time = end_time
            
            # Добавляем оставшуюся часть видео (нормальная скорость)
            if current_time < video.duration:
                final_clip = video.subclip(current_time, video.duration)
                video_clips.append(final_clip)
                self.logger.debug(f"Финальный клип: {current_time:.1f}-{video.duration:.1f}s")
            
            # Объединяем все клипы
            if video_clips:
                adjusted_video = mp.concatenate_videoclips(video_clips)
                self.logger.info(f"Создано видео с корректировкой скорости: {len(video_clips)} сегментов, "
                               f"итоговая длительность: {adjusted_video.duration:.2f}s")
                return adjusted_video
            else:
                self.logger.warning("Не удалось создать клипы, возвращаем оригинальное видео")
                return video
                
        except Exception as e:
            self.logger.error(f"Ошибка корректировки скорости видео: {e}")
            import traceback
            self.logger.error(f"Трассировка:\n{traceback.format_exc()}")
            return video

    def _get_media_duration(self, media_path: str) -> float:
        """
        Получение длительности медиа файла
        
        Args:
            media_path: путь к медиа файлу
            
        Returns:
            float: длительность в секундах
        """
        try:
            import subprocess
            
            cmd = [
                'ffprobe', 
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                media_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration
            else:
                self.logger.warning(f"Не удалось получить длительность {media_path}: {result.stderr}")
                return 0.0
                
        except Exception as e:
            self.logger.error(f"Ошибка получения длительности {media_path}: {e}")
            return 0.0

    def _combine_translated_audio(self, segments: List[dict], video_duration: float,
                                  preserve_original: bool = False, original_audio=None, original_video_path: str = None) -> Optional[str]:
        """
        Объединяет переведенные аудио сегменты в единую дорожку с учетом VAD

        Args:
            segments: список сегментов с переведенным аудио
            video_duration: длительность оригинального видео
            preserve_original: микшировать с оригинальным аудио
            original_audio: оригинальная аудио дорожка
            original_video_path: путь к оригинальному видео для анализа

        Returns:
            str: путь к объединенному аудио файлу
        """
        try:
            self.logger.info(f"🔊 === СОЗДАНИЕ АУДИО ДОРОЖКИ С VAD ФИЛЬТРАЦИЕЙ ===")
            self.logger.info(f"📊 Получено сегментов: {len(segments)}")
            self.logger.info(f"📊 Длительность видео: {video_duration:.2f}s")
            
            self.logger.info(f"=== ДИАГНОСТИКА ВХОДНЫХ СЕГМЕНТОВ С VAD ===")
            for i, segment in enumerate(segments):
                start_time = segment.get('start_time', 0)
                end_time = segment.get('end_time', 0)
                self.logger.info(f"Сегмент {i} [{start_time:.1f}-{end_time:.1f}s]: success={segment.get('success')}, "
                                 f"status={segment.get('status')}, "
                                 f"vad_is_speech={segment.get('vad_is_speech')}, "
                                 f"audio_path={segment.get('translated_audio_path')}")
                if segment.get('translated_audio_path'):
                    exists = Path(segment['translated_audio_path']).exists()
                    self.logger.info(f"  Файл существует: {exists}")
            
            # НОВАЯ ЛОГИКА: Создаем пустое аудио только нужной длительности
            # Сначала определяем максимальную длительность всех РЕЧЕВЫХ сегментов с учетом VAD
            speech_segments = []
            max_end_time = 0
            
            for i, segment in enumerate(segments):
                start_time = segment.get('start_time', 0)
                end_time = segment.get('end_time', 0)
                vad_is_speech = segment.get('vad_is_speech', True)
                status = segment.get('status', '')
                
                # Проверяем VAD результат - пропускаем сегменты без речи
                if not vad_is_speech or status == 'no_speech_vad':
                    self.logger.info(f"❌ ПРОПУСКАЕМ сегмент {i} [{start_time:.1f}-{end_time:.1f}s]: VAD={vad_is_speech}, status={status}")
                    continue
                
                self.logger.info(f"✅ ВКЛЮЧАЕМ речевой сегмент {i} [{start_time:.1f}-{end_time:.1f}s]: VAD={vad_is_speech}")
                if segment.get('end_time'):
                    max_end_time = max(max_end_time, segment.get('end_time', 0))
                    speech_segments.append(segment)
            
            if not speech_segments:
                self.logger.warning("❌ Нет речевых сегментов после VAD фильтрации")
                return None
            
            # НОВАЯ ЛОГИКА: Создаем аудио дорожку ТОЛЬКО из речевых сегментов без базовой тишины
            # Определяем общую длительность на основе максимального времени окончания речевых сегментов
            if not speech_segments:
                self.logger.warning("❌ Нет речевых сегментов для создания аудио")
                return None
            
            # Находим самый поздний речевой сегмент
            max_speech_end = max(seg.get('end_time', 0) for seg in speech_segments)
            
            # Создаем пустые аудио сегменты только в промежутках между речью
            audio_segments = []
            current_time = 0.0
            
            self.logger.info(f"📏 Создание аудио только для речевых сегментов (до {max_speech_end:.2f}s)")
            self.logger.info(f"Обработка {len(speech_segments)} речевых сегментов...")

            # Сортируем речевые сегменты по времени начала
            speech_segments.sort(key=lambda x: x.get('start_time', 0))
            
            # Проверяем, начинается ли первый сегмент с самого начала видео
            first_segment_start = speech_segments[0].get('start_time', 0) if speech_segments else 0
            
            # ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА ОРИГИНАЛЬНОГО АУДИО: 
            # анализируем оригинальное аудио видео, чтобы найти где действительно начинается речь
            detected_silence_duration = 0
            if first_segment_start == 0.0 and original_video_path and speech_segments:
                self.logger.info(f"🔍 АНАЛИЗИРУЕМ оригинальное аудио для поиска начала речи...")
                try:
                    # Загружаем оригинальное аудио из видео
                    import moviepy.editor as mp
                    with mp.VideoFileClip(original_video_path) as video:
                        if video.audio:
                            # Сохраняем первые 60 секунд оригинального аудио во временный файл
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_orig:
                                try:
                                    audio_clip = video.audio.subclip(0, min(60, video.duration))
                                    audio_clip.write_audiofile(tmp_orig.name, verbose=False, logger=None)
                                    audio_clip.close()
                                    
                                    # Анализируем оригинальное аудио на предмет начала речи
                                    orig_audio = AudioSegment.from_file(tmp_orig.name)
                                    self.logger.info(f"🎵 Анализируем первые {len(orig_audio)/1000:.1f}s оригинального аудио")
                                    
                                    # Ищем где начинается значимый сигнал (речь)
                                    for ms in range(0, min(len(orig_audio), 45000), 500):  # Проверяем каждые 0.5с до 45с
                                        segment_500ms = orig_audio[ms:ms+500]
                                        if len(segment_500ms) > 0 and segment_500ms.dBFS > -35:  # Нормальный уровень звука
                                            detected_silence_duration = ms
                                            self.logger.info(f"🔇 НАЙДЕНО начало речи в оригинале на {ms/1000:.1f}s")
                                            break
                                    
                                    if detected_silence_duration == 0:
                                        self.logger.info(f"🎤 В оригинальном аудио речь идет с самого начала")
                                    
                                    Path(tmp_orig.name).unlink()  # Удаляем временный файл
                                    
                                except Exception as e:
                                    self.logger.warning(f"Ошибка анализа оригинального аудио: {e}")
                        else:
                            self.logger.warning(f"Оригинальное видео не содержит аудио")
                except Exception as e:
                    self.logger.warning(f"Ошибка загрузки оригинального видео: {e}")
            
            # Если обнаружена тишина в оригинале, добавляем её
            if detected_silence_duration > 0:
                self.logger.info(f"🔇 ДОБАВЛЯЕМ ДЕТЕКТИРОВАННУЮ ТИШИНУ: 0.0-{detected_silence_duration/1000:.1f}s")
                audio_segments.append(AudioSegment.silent(duration=detected_silence_duration))
                current_time = detected_silence_duration / 1000.0
            elif first_segment_start == 0.0 and speech_segments:
                # Дополнительная проверка переведенного файла (оригинальная логика)
                first_audio_path = speech_segments[0].get('translated_audio_path')
                if first_audio_path and Path(first_audio_path).exists():
                    # Анализируем начало первого сегмента на наличие тишины
                    try:
                        first_audio = AudioSegment.from_file(first_audio_path)
                        # Проверяем первые 5 секунд аудио на наличие значимого сигнала
                        if len(first_audio) > 5000:  # Если сегмент больше 5 секунд
                            first_5_seconds = first_audio[:5000]  # Первые 5 секунд
                            if first_5_seconds.dBFS < -50:  # Очень тихий сигнал
                                # Найдем где начинается реальный сигнал
                                for ms in range(0, min(len(first_audio), 30000), 1000):  # Проверяем до 30 секунд
                                    segment_1s = first_audio[ms:ms+1000]
                                    if segment_1s.dBFS > -40:  # Нашли нормальный сигнал
                                        silence_duration = ms
                                        self.logger.info(f"🔇 ОБНАРУЖЕНА ТИШИНА в начале первого сегмента: добавляем {silence_duration/1000:.1f}s тишины")
                                        audio_segments.append(AudioSegment.silent(duration=silence_duration))
                                        current_time = silence_duration / 1000.0
                                        break
                            else:
                                self.logger.info(f"🎤 Первый сегмент содержит сигнал с начала - тишина не нужна")
                        else:
                            self.logger.info(f"🎤 Первый сегмент слишком короткий для анализа")
                    except Exception as e:
                        self.logger.warning(f"Ошибка анализа первого сегмента: {e}")
                        
            elif first_segment_start > 0:
                initial_silence_duration = first_segment_start * 1000  # в мс
                self.logger.info(f"🔇 ДОБАВЛЯЕМ НАЧАЛЬНУЮ ТИШИНУ: 0.0-{first_segment_start:.1f}s ({initial_silence_duration/1000:.1f}s)")
                audio_segments.append(AudioSegment.silent(duration=int(initial_silence_duration)))
                current_time = first_segment_start
            else:
                self.logger.info(f"🎤 Первый речевой сегмент начинается с {first_segment_start:.1f}s - проверим на принудительную тишину")
            
            successful_segments = 0
            for segment in speech_segments:
                try:
                    # Проверяем только речевые сегменты
                    audio_path = segment.get('translated_audio_path')
                    success = segment.get('success')
                    status = segment.get('status')

                    # Проверяем наличие аудио файла и успешность обработки
                    if not audio_path or not Path(audio_path).exists():
                        self.logger.debug(f"Пропуск сегмента: нет аудио файла")
                        continue

                    # Проверяем статус успешности
                    if success is False or status == 'error' or status == 'no_speech':
                        self.logger.debug(f"Пропуск сегмента: success={success}, status={status}")
                        continue

                    # Загружаем переведенный сегмент
                    segment_audio = AudioSegment.from_file(audio_path)
                    start_time = segment.get('start_time', 0)
                    end_time = segment.get('end_time', start_time + len(segment_audio) / 1000.0)
                    
                    self.logger.debug(f"Обработка сегмента {start_time:.1f}-{end_time:.1f}s: {len(segment_audio)}ms")

                    # Добавляем тишину от текущего времени до начала сегмента (если есть пропуск)
                    if current_time < start_time:
                        silence_duration = (start_time - current_time) * 1000  # в мс
                        self.logger.debug(f"Добавляем тишину: {current_time:.1f}-{start_time:.1f}s ({silence_duration/1000:.1f}s)")
                        audio_segments.append(AudioSegment.silent(duration=int(silence_duration)))

                    # Нормализуем сегмент если очень тихий
                    if segment_audio.dBFS < -50:
                        segment_audio = segment_audio.normalize(headroom=20.0)

                    # Добавляем речевой сегмент
                    audio_segments.append(segment_audio)
                    current_time = end_time
                    successful_segments += 1
                    
                    self.logger.debug(f"Добавлен речевой сегмент: {start_time:.1f}-{end_time:.1f}s")

                except Exception as e:
                    self.logger.warning(f"Ошибка обработки сегмента: {e}")
                    continue

            if successful_segments == 0:
                self.logger.warning("Ни один сегмент не был успешно добавлен")
                return None

            # Объединяем все аудио сегменты
            if not audio_segments:
                self.logger.warning("Нет аудио сегментов для объединения")
                return None
                
            self.logger.info(f"Объединение {len(audio_segments)} аудио сегментов...")
            final_audio = audio_segments[0]
            for segment in audio_segments[1:]:
                final_audio = final_audio + segment

            # Добавляем тишину в конце до полной длительности видео (если речь закончилась раньше)
            if current_time < video_duration:
                end_silence_duration = (video_duration - current_time) * 1000  # в мс
                self.logger.info(f"Добавляем финальную тишину: {current_time:.1f}-{video_duration:.1f}s ({end_silence_duration/1000:.1f}s)")
                final_audio = final_audio + AudioSegment.silent(duration=int(end_silence_duration))

            # Микширование с оригинальным аудио если нужно
            if preserve_original and original_audio:
                try:
                    # Сохраняем оригинальное аудио во временный файл
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_orig:
                        original_audio.write_audiofile(tmp_orig.name, verbose=False, logger=None)
                        original_segment = AudioSegment.from_file(tmp_orig.name)

                        # Понижаем громкость оригинала и микшируем
                        original_segment = original_segment - 15  # -15 dB
                        final_audio = final_audio.overlay(original_segment)

                        # Удаляем временный файл
                        Path(tmp_orig.name).unlink()

                    self.logger.info("Оригинальное аудио добавлено как фон")
                except Exception as e:
                    self.logger.warning(f"Ошибка микширования с оригиналом: {e}")

            # Финальная нормализация громкости
            current_dBFS = final_audio.dBFS
            self.logger.info(f"Громкость до финальной нормализации: {current_dBFS:.1f} dBFS")
            
            if current_dBFS < -30:
                # Для любого тихого аудио применяем полную нормализацию
                final_audio = final_audio.normalize(headroom=20.0)
                self.logger.info(f"Применена полная нормализация аудио")

            # Сохраняем финальное аудио
            final_audio_filename = f"final_audio_{uuid.uuid4().hex}.wav"
            temp_dir = Path(__file__).parent.parent / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            final_audio_path = temp_dir / final_audio_filename
            # Сохраняем финальное аудио
            # final_audio_filename = f"final_audio_{uuid.uuid4().hex}.wav"
            # temp_dir = Path("src/temp")
            # temp_dir.mkdir(exist_ok=True)
            # final_audio_path = temp_dir / final_audio_filename

            final_audio.export(str(final_audio_path), format="wav")
            
            # Диагностика финального аудио
            final_dBFS = final_audio.dBFS
            self.logger.info(f"Финальная громкость аудио: {final_dBFS:.1f} dBFS")

            # Добавляем в список для очистки
            self.temp_files.append(str(final_audio_path))

            self.logger.info(f"Финальное аудио создано: {final_audio_path} ({successful_segments} сегментов)")
            return str(final_audio_path)

        except Exception as e:
            self.logger.error(f"Ошибка объединения аудио сегментов: {e}")
            return None

    def cleanup_temp_files(self):
        """Очистка временных файлов"""
        for temp_file in self.temp_files:
            try:
                if Path(temp_file).exists():
                    Path(temp_file).unlink()
                    self.logger.debug(f"Удален временный файл: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Ошибка удаления {temp_file}: {e}")

        self.temp_files.clear()

    def validate_video_file(self, video_path: str) -> dict:
        """
        Проверка видео файла

        Returns:
            dict: результат валидации с детальной информацией
        """
        result = {
            "valid": False,
            "error": None,
            "info": {},
            "recommendations": []
        }

        try:
            if not Path(video_path).exists():
                result["error"] = "file_not_found"
                return result

            # Проверка размера файла
            file_size = Path(video_path).stat().st_size
            if file_size == 0:
                result["error"] = "empty_file"
                return result

            if file_size > 500 * 1024 * 1024:  # 500MB
                result["recommendations"].append("large_file_warning")

            # Загрузка и анализ видео
            video = mp.VideoFileClip(video_path)

            result["info"] = {
                "duration": video.duration,
                "fps": video.fps,
                "size": video.size,
                "has_audio": video.audio is not None,
                "file_size_mb": file_size / (1024 * 1024)
            }

            # Проверки и рекомендации
            if not video.audio:
                result["error"] = "no_audio"
                video.close()
                return result

            if video.duration > 300:  # 5 минут
                result["recommendations"].append("long_video_warning")

            if video.duration < 1:
                result["recommendations"].append("very_short_video")

            video.close()
            result["valid"] = True

        except Exception as e:
            result["error"] = f"validation_error: {str(e)}"

        return result

    def get_video_info(self, video_path: str) -> dict:
        """Получение подробной информации о видео файле"""
        try:
            video = mp.VideoFileClip(video_path)

            info = {
                "file_path": video_path,
                "file_size_bytes": Path(video_path).stat().st_size,
                "file_size_mb": Path(video_path).stat().st_size / (1024 * 1024),
                "duration_seconds": video.duration,
                "fps": video.fps,
                "resolution": video.size,
                "has_audio": video.audio is not None,
                "estimated_frames": int(video.duration * video.fps) if video.fps else 0
            }

            if video.audio:
                # Дополнительная информация об аудио
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                    video.audio.write_audiofile(tmp_file.name, verbose=False, logger=None)
                    audio_segment = AudioSegment.from_file(tmp_file.name)

                    info["audio_info"] = {
                        "sample_rate": audio_segment.frame_rate,
                        "channels": audio_segment.channels,
                        "sample_width": audio_segment.sample_width,
                        "duration_ms": len(audio_segment),
                        "loudness_dbfs": audio_segment.dBFS
                    }

                    # Удаляем временный файл
                    Path(tmp_file.name).unlink()

            video.close()
            return info

        except Exception as e:
            self.logger.error(f"Ошибка получения информации о видео: {e}")
            return {"error": str(e)}

    def create_synchronized_video_blocks(self, original_video_path: str, 
                                       translated_audio_segments: List[dict],
                                       output_dir: str) -> List[str]:
        """
        Нарезает видео на блоки и синхронизирует каждый блок с соответствующим аудио
        Сохраняет только части видео с речью (согласно VAD), пропускает части без речи
        
        Args:
            original_video_path: путь к оригинальному видео
            translated_audio_segments: список сегментов с переведенным аудио
            output_dir: директория для сохранения блоков
            
        Returns:
            List[str]: список путей к созданным видео блокам
        """
        video_clips = []
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.logger.info("=== СОЗДАНИЕ СИНХРОНИЗИРОВАННЫХ ВИДЕО БЛОКОВ С VAD ===")
            
            # Загружаем оригинальное видео
            video = mp.VideoFileClip(original_video_path)
            self.logger.info(f"Исходное видео: {video.duration:.2f}s")
            
            # Фильтруем сегменты по VAD - оставляем только с речью
            speech_segments = sorted(
                [s for s in translated_audio_segments 
                 if s.get('translated_audio_path') and s.get('vad_is_speech', True) and s.get('status') != 'no_speech_vad'], 
                key=lambda x: x.get('start_time', 0)
            )
            
            self.logger.info(f"Обрабатываем {len(speech_segments)} речевых сегментов (после VAD фильтрации)")
            
            # Показываем какие сегменты пропускаем
            skipped_segments = [s for s in translated_audio_segments 
                              if not s.get('vad_is_speech', True) or s.get('status') == 'no_speech_vad']
            for segment in skipped_segments:
                start = segment.get('start_time', 0)
                end = segment.get('end_time', 0)
                reason = segment.get('vad_reason', 'нет VAD данных')
                self.logger.info(f"⏭️ Пропускаем сегмент {start:.1f}-{end:.1f}s: {reason}")
            
            block_counter = 1
            
            # Обрабатываем только речевые сегменты (VAD уже отфильтровал немые части)
            for i, segment in enumerate(speech_segments):
                try:
                    start_time = segment.get('start_time', 0)
                    end_time = segment.get('end_time', start_time + 5)
                    
                    # ОБРАБАТЫВАЕМ ТОЛЬКО РЕЧЕВОЙ СЕГМЕНТ (без немых частей)
                    audio_path = segment.get('translated_audio_path')
                    if not audio_path or not Path(audio_path).exists():
                        self.logger.warning(f"Пропускаем речевой сегмент {i}: нет аудио файла")
                        continue
                    
                    original_duration = end_time - start_time
                    
                    # Получаем реальную длительность переведенного аудио
                    from pydub import AudioSegment
                    audio_segment = AudioSegment.from_file(audio_path)
                    translated_duration = len(audio_segment) / 1000.0
                    
                    self.logger.info(f"Речевой блок {block_counter}: {start_time:.2f}-{end_time:.2f}s -> перевод {translated_duration:.2f}s")
                    
                    # Вырезаем соответствующий кусок видео
                    video_segment = video.subclip(start_time, end_time)
                    
                    # Растягиваем или сжимаем видео под длительность аудио
                    speed_factor = original_duration / translated_duration
                    
                    if abs(speed_factor - 1.0) > 0.05:  # Если разница больше 5%
                        self.logger.info(f"  Корректируем скорость видео: фактор {speed_factor:.3f}")
                        from moviepy.video.fx.speedx import speedx
                        adjusted_video = video_segment.fx(speedx, speed_factor)
                    else:
                        adjusted_video = video_segment
                    
                    # Загружаем переведенное аудио
                    translated_audio = mp.AudioFileClip(audio_path)
                    
                    # Объединяем видео с переведенным аудио
                    final_segment = adjusted_video.set_audio(translated_audio)
                    
                    # Сохраняем блок
                    speech_filename = f"block_{block_counter:03d}_{segment.get('speaker', 'unknown')}.mp4"
                    speech_path = output_dir / speech_filename
                    
                    final_segment.write_videofile(
                        str(speech_path),
                        codec='libx264',
                        audio_codec='aac',
                        verbose=False,
                        logger=None
                    )
                    
                    # Освобождаем ресурсы
                    video_segment.close()
                    if 'adjusted_video' in locals():
                        adjusted_video.close()
                    translated_audio.close()
                    final_segment.close()
                    
                    video_clips.append(str(speech_path))
                    block_counter += 1
                    
                except Exception as e:
                    self.logger.error(f"❌ Ошибка создания блока {block_counter}: {e}")
                    continue
            
            video.close()
            
            self.logger.info(f"🎬 Создано {len(video_clips)} синхронизированных блоков")
            return video_clips
            
        except Exception as e:
            self.logger.error(f"❌ Критическая ошибка создания блоков: {e}")
            if 'video' in locals():
                video.close()
            return []
    
    def combine_video_blocks(self, video_blocks: List[str], output_path: str) -> bool:
        """
        Объединяет видео блоки в финальное видео
        
        Args:
            video_blocks: список путей к видео блокам
            output_path: путь для сохранения финального видео
            
        Returns:
            bool: успех операции
        """
        try:
            self.logger.info("=== ОБЪЕДИНЕНИЕ ВИДЕО БЛОКОВ ===")
            
            if not video_blocks:
                self.logger.error("Нет блоков для объединения")
                return False
            
            # Загружаем все блоки
            clips = []
            total_duration = 0
            
            for i, block_path in enumerate(video_blocks):
                if not Path(block_path).exists():
                    self.logger.warning(f"Блок не найден: {block_path}")
                    continue
                
                clip = mp.VideoFileClip(block_path)
                clips.append(clip)
                total_duration += clip.duration
                self.logger.debug(f"Блок {i+1}: {clip.duration:.2f}s")
            
            if not clips:
                self.logger.error("Не удалось загрузить ни одного блока")
                return False
            
            self.logger.info(f"Объединяем {len(clips)} блоков, общая длительность: {total_duration:.2f}s")
            
            # Объединяем все клипы
            final_video = mp.concatenate_videoclips(clips)
            
            # Сохраняем финальное видео
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            
            # Освобождаем ресурсы
            for clip in clips:
                clip.close()
            final_video.close()
            
            # Проверяем результат
            if Path(output_path).exists():
                file_size = Path(output_path).stat().st_size / (1024 * 1024)
                self.logger.info(f"✅ Финальное видео создано: {output_path}")
                self.logger.info(f"  Размер: {file_size:.1f} MB")
                
                # Проверяем длительность
                test_video = mp.VideoFileClip(output_path)
                self.logger.info(f"  Итоговая длительность: {test_video.duration:.2f}s")
                test_video.close()
                
                return True
            else:
                self.logger.error("Финальное видео не создано")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка объединения блоков: {e}")
            return False

    def __del__(self):
        """Деструктор для очистки временных файлов"""
        self.cleanup_temp_files()


# Функция для тестирования модуля
def test_video_processor():
    """Тестирование VideoProcessor"""
    processor = VideoProcessor()

    # Пример использования
    print("=== Тестирование VideoProcessor ===")

    test_video = "test_video.mp4"
    if Path(test_video).exists():
        # Валидация видео
        validation = processor.validate_video_file(test_video)
        print(f"Валидация: {validation}")

        # Информация о видео
        info = processor.get_video_info(test_video)
        print(f"Информация о видео: {info}")

        # Извлечение аудио
        audio_path, video_info = processor.extract_audio(test_video)
        if audio_path:
            print(f"Аудио извлечено: {audio_path}")

        # Очистка
        processor.cleanup_temp_files()
    else:
        print(f"Для тестирования поместите видео файл: {test_video}")


if __name__ == "__main__":
    test_video_processor()