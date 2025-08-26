#!/usr/bin/env python3
"""
Точка входа приложения Video-Translator
"""

import sys
import threading
import time
from pathlib import Path

# Добавляем src в Python path если запускаем не из src/
if Path(__file__).parent.name != 'src':
    src_path = Path(__file__).parent / 'src'
    if src_path.exists():
        sys.path.insert(0, str(src_path))

from config import config
from web_app import VideoTranslatorApp
from video_translator import VideoTranslator


def cleanup_scheduler(app_instance: VideoTranslatorApp):
    """Планировщик очистки старых задач"""
    while True:
        time.sleep(3600)  # Каждый час
        try:
            app_instance.cleanup_old_tasks(max_age_hours=24)
        except Exception as e:
            print(f"Ошибка планировщика очистки: {e}")


def main():
    """Главная функция запуска приложения"""
    print("🚀 Запуск Video-Translator...")
    print(f"📁 Версия конфигурации: {config.__class__.__name__}")

    # Создание и настройка приложения
    try:
        app_instance = VideoTranslatorApp()

        # Вывод информации о конфигурации
        print(f"📂 Uploads: {config.UPLOAD_FOLDER}")
        print(f"📂 Outputs: {config.OUTPUT_FOLDER}")
        print(f"📂 Temp: {config.TEMP_FOLDER}")
        print(f"📂 Logs: {config.LOGS_FOLDER}")
        print(f"📂 Templates: {config.TEMPLATES_FOLDER}")
        print(f"📂 Static: {config.STATIC_FOLDER}")

        # Проверка переводчика
        translator_status = app_instance.video_translator.get_translator_status()
        print(f"🔤 Переводчик: {translator_status['type']} ({translator_status['description']})")

        if translator_status['type'] == 'mock':
            print("⚠️  ВНИМАНИЕ: Используется заглушка переводчика!")
            print("   Для полной функциональности настройте API ключи в .env файле")

        print(f"🌐 Приложение доступно по адресу: http://127.0.0.1:5000")
        print("📝 Нажмите Ctrl+C для остановки")

        # Запуск планировщика очистки в отдельном потоке
        cleanup_thread = threading.Thread(target=cleanup_scheduler, args=(app_instance,))
        cleanup_thread.daemon = True
        cleanup_thread.start()

        # Запуск Flask приложения
        app_instance.run(
            host='127.0.0.1',
            port=5000,
            debug=True
        )

    except KeyboardInterrupt:
        print("\n👋 Остановка приложения...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


def test_components():
    """Тестирование основных компонентов"""
    print("🧪 Тестирование компонентов...")

    # Тест конфигурации
    print(f"✓ Конфигурация: {config}")

    # Тест VideoTranslator
    try:
        translator = VideoTranslator()
        status = translator.get_translator_status()
        print(f"✓ VideoTranslator: {status['type']}")
    except Exception as e:
        print(f"❌ VideoTranslator: {e}")
        return False

    # Тест Flask приложения
    try:
        app_instance = VideoTranslatorApp()
        print(f"✓ Flask App: Готово")
    except Exception as e:
        print(f"❌ Flask App: {e}")
        return False

    return True


if __name__ == '__main__':
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            success = test_components()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == '--help':
            print("""
Video-Translator - Переводчик видео с английского на русский

Использование:
    python app.py           - Запуск веб-приложения
    python app.py --test    - Тестирование компонентов
    python app.py --help    - Показать справку

Переменные окружения (.env):
    FLASK_SECRET_KEY        - Секретный ключ Flask
    MAX_FILE_SIZE_MB        - Максимальный размер файла (MB)
    MAX_DURATION_MINUTES    - Максимальная длительность видео (минуты)
    LOG_LEVEL              - Уровень логирования (INFO, DEBUG, ERROR)

    GOOGLE_SPEECH_API_KEY   - Google Speech-to-Text API ключ
    GOOGLE_TRANSLATE_API_KEY - Google Translate API ключ  
    GOOGLE_TTS_API_KEY     - Google Text-to-Speech API ключ
    DEEPL_API_KEY          - DeepL API ключ (опционально)
    ELEVENLABS_API_KEY     - ElevenLabs API ключ (опционально)

Структура проекта:
    src/
    ├── app.py              - Точка входа
    ├── config.py           - Конфигурация
    ├── video_translator.py - Основной класс
    ├── web_app.py          - Flask приложение
    └── translator_compat.py - Универсальный переводчик

    uploads/    - Загруженные видео
    outputs/    - Переведенные видео  
    logs/       - Логи приложения
    templates/  - HTML шаблоны
    static/     - CSS/JS файлы
            """)
            sys.exit(0)
        else:
            print(f"Неизвестный аргумент: {sys.argv[1]}")
            print("Используйте --help для справки")
            sys.exit(1)

    # Обычный запуск приложения
    main()