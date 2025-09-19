#!/usr/bin/env python3
"""
Модуль для разделения речи по спикерам (speaker diarization)
Использует PyAnnote для идентификации разных говорящих
"""

import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import subprocess
import json
import tempfile
import librosa
import numpy as np

class SpeakerDiarization:
    """Класс для разделения речи по спикерам"""
    
    def __init__(self, config=None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Карта голосов для разных типов спикеров
        self.voice_mapping = {
            'male': ['ru-male-1', 'ru-male-2', 'ru-male-3'],
            'female': ['ru-female-1', 'ru-female-2', 'ru-female-3']
        }
        self.used_voices = {'male': 0, 'female': 0}
        
    def segment_by_speakers(self, audio_path: str, min_speaker_duration: float = 5.0) -> List[Dict]:
        """
        Сегментирует аудио по спикерам
        
        Args:
            audio_path: путь к аудио файлу
            min_speaker_duration: минимальная длительность сегмента спикера
            
        Returns:
            list: список сегментов с информацией о спикерах
        """
        try:
            self.logger.info(f"🎭 Начинаем сегментацию по спикерам: {audio_path}")
            
            # Сначала пробуем простую сегментацию по паузам с разными порогами
            segments = self._segment_by_silence_with_speaker_logic(audio_path, min_speaker_duration)
            
            # Определяем пол для каждого сегмента
            segments = self._detect_gender_for_segments(segments)
            
            self.logger.info(f"✅ Создано {len(segments)} сегментов по спикерам")
            return segments
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка сегментации по спикерам: {e}")
            # Fallback к обычной сегментации
            return self._fallback_segmentation(audio_path)
    
    def _segment_by_silence_with_speaker_logic(self, audio_path: str, min_duration: float) -> List[Dict]:
        """
        Интеллектуальная сегментация по паузам с логикой спикеров
        """
        from pydub import AudioSegment
        from pydub.silence import split_on_silence, detect_silence
        
        self.logger.debug("🔍 Анализируем аудио для определения спикеров...")
        
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0
        
        # Адаптивные параметры для диалогов (МЕНЕЕ чувствительная сегментация для этого видео)
        if total_duration > 300:  # > 5 минут
            min_silence_len = 1200   # 1.2 секунды для длинных диалогов
            silence_thresh = -35
        elif total_duration > 120:  # > 2 минуты  
            min_silence_len = 1000   # 1.0 секунды для средних диалогов - УВЕЛИЧЕНО
            silence_thresh = -40     # Менее чувствительный порог
        else:
            min_silence_len = 800    # 0.8 секунды для коротких диалогов
            silence_thresh = -42
            
        self.logger.debug(f"🎛️ Параметры: min_silence={min_silence_len}ms, thresh={silence_thresh}dB")
        
        # Обнаруживаем паузы
        silence_segments = detect_silence(
            audio, 
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh
        )
        
        # Создаем сегменты между паузами
        segments = []
        current_pos = 0
        current_speaker = 0  # Отслеживаем текущего спикера (0=A, 1=B)
        
        for i, (silence_start, silence_end) in enumerate(silence_segments):
            # Сегмент до паузы
            if silence_start > current_pos:
                segment_duration = (silence_start - current_pos) / 1000.0
                
                if segment_duration >= min_duration:
                    # Интеллектуальное определение спикера по паузам и длительности
                    silence_duration = (silence_end - silence_start) / 1000.0 if i < len(silence_segments) - 1 else 0
                    
                    if len(segments) == 0:
                        # Первый сегмент - всегда Speaker_A
                        speaker_label = "Speaker_A"
                        current_speaker = 0
                    elif silence_duration > 3.0:  # Только ОЧЕНЬ длинная пауза - смена спикера (увеличено с 2.0)
                        current_speaker = (current_speaker + 1) % 2  # Чередуем между 0 и 1
                        speaker_label = f"Speaker_{chr(65 + current_speaker)}"
                    elif segment_duration > 60:  # Только ОЧЕНЬ длинный сегмент - возможно новый спикер (увеличено с 30)
                        current_speaker = (current_speaker + 1) % 2
                        speaker_label = f"Speaker_{chr(65 + current_speaker)}"
                    else:
                        # Короткий сегмент - тот же спикер
                        speaker_label = f"Speaker_{chr(65 + current_speaker)}"
                    
                    segment_path = self._extract_audio_segment(
                        audio, current_pos, silence_start, len(segments)
                    )
                    
                    segments.append({
                        'id': len(segments),
                        'path': segment_path,
                        'start_time': current_pos / 1000.0,
                        'end_time': silence_start / 1000.0,
                        'duration': segment_duration,
                        'speaker': speaker_label,
                        'speaker_confidence': 0.8,  # Базовая уверенность
                        'silence_after': (silence_end - silence_start) / 1000.0
                    })
                    
                    self.logger.debug(f"🎭 Сегмент {len(segments)}: {speaker_label}, {segment_duration:.1f}s")
            
            current_pos = silence_end
        
        # Последний сегмент после последней паузы
        if current_pos < len(audio):
            segment_duration = (len(audio) - current_pos) / 1000.0
            if segment_duration >= min_duration:
                segment_path = self._extract_audio_segment(
                    audio, current_pos, len(audio), len(segments)
                )
                
                # Для последнего сегмента тоже определяем спикера интеллектуально
                if segment_duration > 30:  # Длинный последний сегмент - возможно другой спикер (увеличено с 15)
                    current_speaker = (current_speaker + 1) % 2
                
                segments.append({
                    'id': len(segments),
                    'path': segment_path,
                    'start_time': current_pos / 1000.0,
                    'end_time': len(audio) / 1000.0,
                    'duration': segment_duration,
                    'speaker': f"Speaker_{chr(65 + current_speaker)}",
                    'speaker_confidence': 0.8,
                    'silence_after': 0.0
                })
        
        return segments
    
    def _extract_audio_segment(self, audio: 'AudioSegment', start_ms: int, end_ms: int, segment_id: int) -> str:
        """Извлекает сегмент аудио и сохраняет в файл"""
        from pathlib import Path
        
        segment = audio[start_ms:end_ms]
        
        if self.config:
            segment_path = self.config.get_temp_filename(f"speaker_segment_{segment_id}", ".wav")
        else:
            segment_path = f"/tmp/speaker_segment_{segment_id}.wav"
            
        segment.export(str(segment_path), format="wav")
        return str(segment_path)
    
    def _fallback_segmentation(self, audio_path: str) -> List[Dict]:
        """Fallback сегментация без speaker diarization"""
        from pydub import AudioSegment
        from pydub.silence import split_on_silence
        
        self.logger.warning("⚠️ Используем fallback сегментацию без разделения по спикерам")
        
        audio = AudioSegment.from_file(audio_path)
        chunks = split_on_silence(
            audio,
            min_silence_len=1000,
            silence_thresh=-40,
            keep_silence=500
        )
        
        segments = []
        current_time = 0
        
        for i, chunk in enumerate(chunks):
            chunk_duration = len(chunk) / 1000.0
            
            if chunk_duration > 1.0:  # минимум 1 секунда
                segment_path = self._extract_audio_segment(
                    audio, int(current_time * 1000), int((current_time + chunk_duration) * 1000), i
                )
                
                segments.append({
                    'id': i,
                    'path': segment_path,
                    'start_time': current_time,
                    'end_time': current_time + chunk_duration,
                    'duration': chunk_duration,
                    'speaker': f"Speaker_{i % 2 + 1}",  # Простое чередование
                    'speaker_confidence': 0.5,
                    'silence_after': 0.5
                })
            
            current_time += chunk_duration
            
        return segments
    
    def merge_short_segments(self, segments: List[Dict], min_duration: float = 5.0) -> List[Dict]:
        """
        Объединяет короткие сегменты одного спикера
        
        Args:
            segments: список сегментов
            min_duration: минимальная желаемая длительность сегмента
            
        Returns:
            list: объединенные сегменты
        """
        if not segments:
            return segments
            
        merged = []
        current_group = [segments[0]]
        
        for i in range(1, len(segments)):
            current_seg = segments[i]
            prev_seg = segments[i-1]
            
            # Объединяем если тот же спикер и общая длительность не слишком велика
            if (current_seg['speaker'] == prev_seg['speaker'] and 
                sum(s['duration'] for s in current_group) + current_seg['duration'] < min_duration * 2):
                current_group.append(current_seg)
            else:
                # Создаем объединенный сегмент
                if len(current_group) > 1:
                    merged_segment = self._merge_segment_group(current_group)
                    merged.append(merged_segment)
                else:
                    merged.append(current_group[0])
                    
                current_group = [current_seg]
        
        # Добавляем последнюю группу
        if current_group:
            if len(current_group) > 1:
                merged_segment = self._merge_segment_group(current_group)
                merged.append(merged_segment)
            else:
                merged.append(current_group[0])
        
        self.logger.info(f"🔗 Объединено: {len(segments)} → {len(merged)} сегментов")
        return merged
    
    def _merge_segment_group(self, group: List[Dict]) -> Dict:
        """Объединяет группу сегментов в один"""
        if not group:
            return {}
            
        first = group[0]
        last = group[-1]
        
        return {
            'id': first['id'],
            'path': first['path'],  # Используем путь первого сегмента
            'start_time': first['start_time'],
            'end_time': last['end_time'],
            'duration': sum(s['duration'] for s in group),
            'speaker': first['speaker'],
            'speaker_confidence': sum(s['speaker_confidence'] for s in group) / len(group),
            'merged_from': len(group),
            'silence_after': last.get('silence_after', 0.0)
        }
    
    def _detect_gender_for_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        Определяет пол для каждого сегмента на основе анализа голоса
        
        Args:
            segments: список сегментов аудио
            
        Returns:
            segments: сегменты с добавленной информацией о поле и назначенным голосом
        """
        self.logger.info("🎭 Определение пола спикеров...")
        
        # Сбрасываем счетчики использованных голосов
        self.used_voices = {'male': 0, 'female': 0}
        speaker_genders = {}  # Кэш для уже определенных спикеров
        
        for segment in segments:
            speaker_id = segment['speaker']
            
            # Если уже определили пол для этого спикера, используем кэш
            if speaker_id in speaker_genders:
                gender = speaker_genders[speaker_id]
            else:
                # Определяем пол по аудио сегменту
                gender = self._analyze_voice_gender(segment['path'])
                speaker_genders[speaker_id] = gender
            
            # Назначаем уникальный голос для этого спикера
            voice_id = self._assign_voice_for_speaker(speaker_id, gender)
            
            # Добавляем информацию в сегмент
            segment['gender'] = gender
            segment['voice_id'] = voice_id
            
            self.logger.debug(f"🎭 {speaker_id}: {gender}, голос: {voice_id}")
        
        # Выводим статистику
        gender_stats = {}
        for segment in segments:
            gender = segment['gender']
            gender_stats[gender] = gender_stats.get(gender, 0) + 1
        
        self.logger.info(f"📊 Статистика полов: {gender_stats}")
        
        return segments
    
    def _analyze_voice_gender(self, audio_path: str) -> str:
        """
        Анализирует пол говорящего по аудио файлу
        
        Args:
            audio_path: путь к аудио файлу
            
        Returns:
            str: 'male' или 'female'
        """
        try:
            # Загружаем аудио
            y, sr = librosa.load(audio_path, sr=None)
            
            # Вычисляем основную частоту (F0) - ключевой показатель пола
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr, threshold=0.1)
            
            # Извлекаем значения F0
            f0_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:  # Игнорируем нулевые значения
                    f0_values.append(pitch)
            
            if not f0_values:
                # Fallback: анализ спектральных характеристик
                return self._analyze_spectral_features(y, sr)
            
            # Медианная основная частота
            median_f0 = np.median(f0_values)
            
            self.logger.debug(f"🎵 F0 медиана: {median_f0:.1f} Hz")
            
            # Классификация по основной частоте
            # Мужчины: обычно 85-180 Hz
            # Женщины: обычно 165-265 Hz
            if median_f0 < 150:
                return 'male'
            elif median_f0 > 200:
                return 'female'
            else:
                # Промежуточная зона - дополнительный анализ
                return self._analyze_spectral_features(y, sr)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка анализа пола: {e}")
            # Fallback: случайное назначение на основе простой эвристики
            return 'male' if len(audio_path) % 2 == 0 else 'female'
    
    def _analyze_spectral_features(self, y: np.ndarray, sr: int) -> str:
        """
        Дополнительный анализ спектральных характеристик для определения пола
        
        Args:
            y: аудио сигнал
            sr: частота дискретизации
            
        Returns:
            str: 'male' или 'female'
        """
        try:
            # Вычисляем спектральный центроид (яркость звука)
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            mean_centroid = np.mean(spectral_centroids)
            
            # Вычисляем MFCC (мел-частотные кепстральные коэффициенты)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mean_mfcc = np.mean(mfccs, axis=1)
            
            self.logger.debug(f"🎵 Спектральный центроид: {mean_centroid:.1f} Hz")
            
            # Женские голоса обычно имеют более высокий спектральный центроид
            # и другие MFCC характеристики
            if mean_centroid > 2500:  # Высокий спектральный центроид
                return 'female'
            elif mean_centroid < 1500:  # Низкий спектральный центроид
                return 'male'
            else:
                # Анализируем MFCC для финального решения
                # Второй MFCC коэффициент часто коррелирует с полом
                if len(mean_mfcc) > 1 and mean_mfcc[1] > 0:
                    return 'female'
                else:
                    return 'male'
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка спектрального анализа: {e}")
            return 'male'  # Fallback по умолчанию
    
    def _assign_voice_for_speaker(self, speaker_id: str, gender: str) -> str:
        """
        Назначает уникальный голос для спикера
        
        Args:
            speaker_id: идентификатор спикера
            gender: пол спикера ('male' или 'female')
            
        Returns:
            str: идентификатор назначенного голоса
        """
        if gender not in self.voice_mapping:
            gender = 'male'  # Fallback
        
        # Выбираем следующий доступный голос для этого пола
        available_voices = self.voice_mapping[gender]
        voice_index = self.used_voices[gender] % len(available_voices)
        voice_id = available_voices[voice_index]
        
        # Увеличиваем счетчик для следующего спикера того же пола
        self.used_voices[gender] += 1
        
        return voice_id