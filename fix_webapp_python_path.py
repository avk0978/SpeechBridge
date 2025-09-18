#!/usr/bin/env python3
"""
Исправление пути к Python в веб-приложении для устранения miniforge3 конфликта
"""

import sys
import subprocess
import os
from pathlib import Path

def check_python_paths():
    """Проверка различных путей Python"""
    print("🔍 ПРОВЕРКА ПУТЕЙ PYTHON")
    print("=" * 60)
    
    # Текущий Python
    print(f"📍 Текущий sys.executable: {sys.executable}")
    
    # Проверяем python3 в PATH
    try:
        result = subprocess.run(['which', 'python3'], capture_output=True, text=True)
        if result.returncode == 0:
            python3_path = result.stdout.strip()
            print(f"📍 python3 в PATH: {python3_path}")
        else:
            print("❌ python3 не найден в PATH")
    except Exception as e:
        print(f"❌ Ошибка поиска python3: {e}")
    
    # Проверяем /usr/local/bin/python3
    usr_local_python = "/usr/local/bin/python3"
    if os.path.exists(usr_local_python):
        print(f"✅ Найден: {usr_local_python}")
        
        # Тестируем версию
        try:
            result = subprocess.run([usr_local_python, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   Версия: {result.stdout.strip()}")
        except Exception as e:
            print(f"   ❌ Ошибка проверки версии: {e}")
    else:
        print(f"❌ Не найден: {usr_local_python}")
    
    # Анализируем miniforge
    if "miniforge3" in sys.executable:
        print("⚠️ ВНИМАНИЕ: Используется miniforge3!")
        print("💡 Это может вызывать конфликты с multiprocessing")
        print("🔧 Решение: использовать обычный Python для subprocess")
        return usr_local_python if os.path.exists(usr_local_python) else None
    else:
        print("✅ Используется обычный Python - проблем быть не должно")
        return sys.executable

def test_whisper_with_python_path(python_path):
    """Тест Whisper с конкретным путем Python"""
    print(f"\n🧪 ТЕСТ WHISPER С {python_path}")
    print("=" * 80)
    
    if not python_path or not os.path.exists(python_path):
        print("❌ Путь к Python не найден")
        return False
    
    # Создаем тестовый скрипт
    test_script = '''
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['MKL_NUM_THREADS'] = '1'

import multiprocessing
multiprocessing.set_start_method('spawn', force=True)

try:
    import whisper
    import torch
    import tempfile
    import wave
    import numpy as np
    
    # Создаем тестовый аудио
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        duration = 2
        sample_rate = 16000
        t = np.linspace(0, duration, duration * sample_rate, False)
        wave_data = 0.3 * np.sin(2 * np.pi * 440 * t)
        wave_data_int = (wave_data * 32767).astype(np.int16)
        
        with wave.open(tmp.name, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(wave_data_int.tobytes())
        
        test_file = tmp.name
    
    print("SUBPROCESS: Создан тестовый файл")
    
    # Загружаем модель
    device = "cpu"
    model = whisper.load_model("tiny", device=device)
    print("SUBPROCESS: Модель загружена")
    
    # Транскрипция
    result = model.transcribe(test_file, language="en", verbose=False)
    print(f"SUBPROCESS: Результат получен: {result.get('text', '')}")
    
    # Очистка
    os.unlink(test_file)
    print("SUBPROCESS: Тест завершен успешно")
    
except Exception as e:
    print(f"SUBPROCESS: Ошибка - {e}")
    import traceback
    traceback.print_exc()
'''
    
    # Запускаем тест с указанным Python
    try:
        result = subprocess.run(
            [python_path, '-c', test_script],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(f"🔍 Return code: {result.returncode}")
        print(f"📤 Stdout:")
        for line in result.stdout.splitlines()[-10:]:  # Последние 10 строк
            print(f"   {line}")
        
        if result.stderr:
            print(f"📥 Stderr:")
            for line in result.stderr.splitlines()[-5:]:  # Последние 5 строк
                print(f"   {line}")
        
        if result.returncode == 0:
            print("✅ Whisper работает с этим Python!")
            return True
        elif result.returncode == -11:
            print("❌ Сегментационная ошибка (-11)")
            return False
        else:
            print(f"❌ Другая ошибка: код возврата {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Тест превысил таймаут")
        return False
    except Exception as e:
        print(f"❌ Ошибка запуска теста: {e}")
        return False

def suggest_fix():
    """Предложение исправления"""
    print("\n💡 ПРЕДЛОЖЕНИЕ ИСПРАВЛЕНИЯ")
    print("=" * 60)
    
    print("🔧 Нужно заставить subprocess использовать обычный Python:")
    print("1. Найти в speech_recognizer.py где создается subprocess")
    print("2. Заменить sys.executable на /usr/local/bin/python3")
    print("3. Или добавить переменную окружения PATH")
    
    print("\n📝 Код для исправления:")
    print("""
# Вместо:
result = subprocess.run([sys.executable, script_path], ...)

# Использовать:
python_path = "/usr/local/bin/python3" if os.path.exists("/usr/local/bin/python3") else sys.executable
result = subprocess.run([python_path, script_path], ...)
""")

def main():
    print("🎯 ЦЕЛЬ: Найти правильный Python для устранения miniforge3 конфликта")
    print("🔍 Return code -11 возникает из-за miniforge3 multiprocessing")
    print()
    
    # Проверяем пути
    working_python = check_python_paths()
    
    if working_python and "miniforge3" not in working_python:
        print(f"\n🎯 НАЙДЕН РАБОЧИЙ PYTHON: {working_python}")
        
        # Тестируем его
        if test_whisper_with_python_path(working_python):
            print(f"\n✅ РЕШЕНИЕ НАЙДЕНО!")
            print(f"🔧 Использовать {working_python} вместо sys.executable")
            suggest_fix()
            return True
    
    print("\n❌ Не удалось найти рабочий Python")
    suggest_fix()
    return False

if __name__ == "__main__":
    main()