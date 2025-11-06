# Video Translator with Speech Synchronization

Система автоматического перевода видео с сохранением синхронизации речи.

## Особенности

- ✅ Автоматическая транскрипция речи с помощью OpenAI Whisper
- ✅ Перевод текста через DeepL API
- ✅ Синтез речи на целевом языке (Edge TTS, Google TTS, ElevenLabs)
- ✅ **Автоматическая синхронизация аудио с видео**
  - Сохранение тайминга оригинальной речи
  - Корректная обработка начальной тишины
  - Автоматическое добавление пауз между сегментами
- ✅ Генерация и встраивание субтитров

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/andreykolpakov/Video-Translator.git
cd Video-Translator

# Установить зависимости
pip install -r requirements.txt

# Установить FFmpeg (если еще не установлен)
# macOS:
brew install ffmpeg

# Ubuntu/Debian:
sudo apt-get install ffmpeg
```

## Использование

```bash
# Базовое использование
python3 -m speechbridge.cli translate input.mp4 output.mp4 \
  -t ru \
  --model tiny \
  --sync \
  --subtitles \
  --embed-subtitles

# С настройками DeepL API
export DEEPL_API_KEY="your-api-key"
python3 -m speechbridge.cli translate input.mp4 output.mp4 \
  -t ru \
  --model tiny \
  --sync
```

## Параметры

- `-t, --target-lang` - Целевой язык перевода (ru, en, es, de и т.д.)
- `--model` - Модель Whisper (tiny, base, small, medium, large)
- `--sync` - Включить синхронизацию аудио с оригинальным тайм ингом
- `--subtitles` - Генерировать файлы субтитров (.srt)
- `--embed-subtitles` - Встроить субтитры в видео
- `--keep-temp` - Сохранить временные файлы для отладки

## Архитектура

Проект состоит из модульной системы компонентов:

```
speechbridge/
├── components/
│   ├── audio/
│   │   ├── transcription.py  # Whisper транскрипция
│   │   ├── tts.py            # Синтез речи
│   │   └── sync.py           # Синхронизация аудио ⭐
│   ├── text/
│   │   └── translation.py    # DeepL перевод
│   └── video/
│       ├── ffmpeg_processor.py  # FFmpeg обработка
│       └── subtitles.py         # Генерация субтитров
└── pipeline.py               # Основной пайплайн
```

## Ключевые исправления

### Синхронизация начальной тишины

Система автоматически определяет начало речи в видео и добавляет соответствующую тишину в переведенную аудиодорожку.

**Файл**: `speechbridge/components/audio/sync.py:66-78`

```python
# Detect actual speech start time to correct Whisper timing
actual_speech_start = 0.0
if original_audio_path and segments:
    actual_speech_start = self._detect_speech_start(original_audio_path)

    # If first segment starts before actual speech, adjust it
    if segments[0]['start'] < actual_speech_start - 0.5:  # 500ms tolerance
        self.logger.info(
            f"Detected silence at start: {actual_speech_start:.2f}s "
            f"(Whisper reported: {segments[0]['start']:.2f}s)"
        )
        # Adjust first segment start time
        segments[0]['start'] = actual_speech_start
```

### Синхронизация пауз между сегментами

Паузы и тишина между сегментами речи автоматически сохраняются.

**Файл**: `speechbridge/components/audio/sync.py:232-256`

## Лицензия

MIT

## Авторы

- Andrey Kolpakov - [@andreykolpakov](https://github.com/andreykolpakov)

## Благодарности

- OpenAI Whisper
- DeepL API
- Edge TTS
- FFmpeg
