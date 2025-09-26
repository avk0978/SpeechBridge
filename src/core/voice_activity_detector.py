#!/usr/bin/env python3
"""
Voice Activity Detection (VAD) - детекция речи в аудио сегментах
Помогает фильтровать сегменты без речи (тишина, музыка, фоновые звуки)
"""

import logging
import numpy as np
import librosa
from typing import Dict, List, Optional
from pathlib import Path


class VoiceActivityDetector:
    """Детектор речевой активности для фильтрации сегментов без речи"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Пороги для детекции речи
        self.min_speech_energy = 0.01      # Минимальная энергия для считывания сигнала речью
        self.min_spectral_centroid = 1000  # Минимальный спектральный центроид для речи
        self.max_spectral_centroid = 8000  # Максимальный спектральный центроид для речи
        self.min_speech_duration = 0.5     # Минимальная длительность речи в сегменте (секунды)
        self.speech_frequency_ratio = 0.3  # Минимальная доля речевых частот
        
    def is_speech_segment(self, audio_path: str, threshold: float = 0.5) -> Dict[str, any]:
        """
        Определяет, содержит ли аудио сегмент речь
        
        Args:
            audio_path: путь к аудио файлу
            threshold: порог для классификации как речь (0.0-1.0)
            
        Returns:
            dict: результат анализа с метриками и решением
        """
        try:
            # Загружаем аудио
            audio, sr = librosa.load(audio_path, sr=None)
            file_duration = len(audio) / sr if sr > 0 else 0
            
            self.logger.debug(f"🔍 VAD анализ {Path(audio_path).name}: длительность={file_duration:.2f}s, семплов={len(audio)}")
            
            if len(audio) == 0:
                return {
                    'is_speech': False,
                    'confidence': 0.0,
                    'reason': 'empty_audio',
                    'metrics': {}
                }
            
            # Вычисляем различные метрики
            metrics = self._extract_speech_metrics(audio, sr)
            
            # Комбинированная оценка речевой активности
            speech_score = self._calculate_speech_score(metrics)
            
            is_speech = speech_score >= threshold
            
            result = {
                'is_speech': is_speech,
                'confidence': speech_score,
                'reason': self._get_decision_reason(metrics, speech_score, threshold),
                'metrics': metrics
            }
            
            self.logger.debug(f"VAD анализ {Path(audio_path).name}: speech={is_speech}, confidence={speech_score:.3f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка VAD анализа {audio_path}: {e}")
            return {
                'is_speech': True,  # По умолчанию считаем речью при ошибке
                'confidence': 0.5,
                'reason': f'error: {str(e)}',
                'metrics': {}
            }
    
    def _extract_speech_metrics(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """Извлекает метрики для определения речи"""
        
        # 1. Энергия сигнала (RMS)
        rms_energy = np.mean(librosa.feature.rms(y=audio)[0])
        
        # 2. Спектральный центроид (характеризует "яркость" звука)
        spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)[0])
        
        # 3. Спектральная полоса пропускания
        spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=audio, sr=sr)[0])
        
        # 4. Zero Crossing Rate (частота пересечения нуля)
        zcr = np.mean(librosa.feature.zero_crossing_rate(audio)[0])
        
        # 5. MFCC коэффициенты (характерные для речи)
        mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        mfcc_var = np.var(mfccs, axis=1)  # Вариативность MFCC
        mfcc_mean = np.mean(mfcc_var)
        
        # 6. Спектральный контраст (различие между пиками и долинами в спектре)
        spectral_contrast = np.mean(librosa.feature.spectral_contrast(y=audio, sr=sr))
        
        # 7. Анализ частотного содержимого
        # Речь обычно содержит энергию в диапазоне 85-8000 Hz
        stft = librosa.stft(audio)
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Энергия в речевом диапазоне (85-8000 Hz)
        speech_freq_mask = (freqs >= 85) & (freqs <= 8000)
        speech_energy = np.mean(np.abs(stft[speech_freq_mask, :]))
        total_energy = np.mean(np.abs(stft))
        speech_ratio = speech_energy / (total_energy + 1e-10)
        
        return {
            'rms_energy': float(rms_energy),
            'spectral_centroid': float(spectral_centroid),
            'spectral_bandwidth': float(spectral_bandwidth),
            'zero_crossing_rate': float(zcr),
            'mfcc_variance': float(mfcc_mean),
            'spectral_contrast': float(spectral_contrast),
            'speech_frequency_ratio': float(speech_ratio),
            'duration': len(audio) / sr
        }
    
    def _calculate_speech_score(self, metrics: Dict[str, float]) -> float:
        """Вычисляет комбинированную оценку речевой активности (0.0-1.0)"""
        
        score = 0.0
        weights = {
            'energy': 0.2,
            'spectral': 0.25,
            'frequency': 0.3,
            'mfcc': 0.15,
            'duration': 0.1
        }
        
        # 1. Оценка энергии
        if metrics['rms_energy'] > self.min_speech_energy:
            energy_score = min(1.0, metrics['rms_energy'] / 0.1)  # Нормализуем к 0.1
            score += weights['energy'] * energy_score
        
        # 2. Спектральный анализ
        centroid = metrics['spectral_centroid']
        if self.min_spectral_centroid <= centroid <= self.max_spectral_centroid:
            # Речь обычно имеет центроид в диапазоне 1000-4000 Hz
            spectral_score = 1.0 - abs(centroid - 2500) / 2500  # Оптимум в районе 2500 Hz
            spectral_score = max(0.0, spectral_score)
            score += weights['spectral'] * spectral_score
        
        # 3. Частотный анализ
        if metrics['speech_frequency_ratio'] >= self.speech_frequency_ratio:
            freq_score = min(1.0, metrics['speech_frequency_ratio'] / 0.8)
            score += weights['frequency'] * freq_score
        
        # 4. MFCC вариативность (речь имеет изменчивые характеристики)
        if metrics['mfcc_variance'] > 0.5:
            mfcc_score = min(1.0, metrics['mfcc_variance'] / 2.0)
            score += weights['mfcc'] * mfcc_score
        
        # 5. Длительность (очень короткие сегменты скорее всего не речь)
        if metrics['duration'] >= self.min_speech_duration:
            duration_score = min(1.0, metrics['duration'] / 2.0)  # Полный балл при 2+ секундах
            score += weights['duration'] * duration_score
        
        return min(1.0, score)
    
    def _get_decision_reason(self, metrics: Dict[str, float], score: float, threshold: float) -> str:
        """Возвращает причину принятого решения"""
        
        if score < threshold:
            # Анализируем причины отклонения
            reasons = []
            
            if metrics['rms_energy'] < self.min_speech_energy:
                reasons.append(f"низкая_энергия({metrics['rms_energy']:.3f})")
            
            if metrics['spectral_centroid'] < self.min_spectral_centroid:
                reasons.append(f"низкий_центроид({metrics['spectral_centroid']:.0f}Hz)")
            elif metrics['spectral_centroid'] > self.max_spectral_centroid:
                reasons.append(f"высокий_центроид({metrics['spectral_centroid']:.0f}Hz)")
            
            if metrics['speech_frequency_ratio'] < self.speech_frequency_ratio:
                reasons.append(f"мало_речевых_частот({metrics['speech_frequency_ratio']:.3f})")
            
            if metrics['duration'] < self.min_speech_duration:
                reasons.append(f"короткий_сегмент({metrics['duration']:.1f}s)")
            
            return "не_речь: " + ", ".join(reasons) if reasons else "низкий_общий_счет"
        else:
            return f"речь: счет={score:.3f}"
    
    def filter_speech_segments(self, segments: List[Dict], min_confidence: float = 0.5) -> List[Dict]:
        """
        Фильтрует список сегментов, оставляя только те, что содержат речь
        
        Args:
            segments: список сегментов с путями к аудио файлам
            min_confidence: минимальная уверенность для считывания речью
            
        Returns:
            list: отфильтрованные сегменты с добавленной информацией о VAD
        """
        
        filtered_segments = []
        
        for i, segment in enumerate(segments):
            audio_path = segment.get('path')
            if not audio_path or not Path(audio_path).exists():
                self.logger.warning(f"Сегмент {i+1}: файл не найден {audio_path}")
                continue
            
            # Анализируем речевую активность
            vad_result = self.is_speech_segment(audio_path, min_confidence)
            
            # Добавляем VAD информацию к сегменту
            segment_with_vad = {
                **segment,
                'vad_is_speech': vad_result['is_speech'],
                'vad_confidence': vad_result['confidence'],
                'vad_reason': vad_result['reason'],
                'vad_metrics': vad_result['metrics']
            }
            
            if vad_result['is_speech']:
                filtered_segments.append(segment_with_vad)
                self.logger.info(f"✅ Сегмент {i+1}: РЕЧЬ (уверенность: {vad_result['confidence']:.3f})")
            else:
                self.logger.info(f"❌ Сегмент {i+1}: НЕ РЕЧЬ ({vad_result['reason']})")
                # Все равно добавляем сегмент, но помечаем как no_speech
                segment_with_vad['status'] = 'no_speech_vad'
                filtered_segments.append(segment_with_vad)
        
        speech_count = sum(1 for seg in filtered_segments if seg.get('vad_is_speech', False))
        self.logger.info(f"🎯 VAD фильтрация: {speech_count}/{len(segments)} сегментов содержат речь")
        
        return filtered_segments