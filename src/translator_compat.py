"""
Универсальный переводчик для Video-Translator
"""

import logging

# Глобальные переменные
TRANSLATOR_TYPE = None
translator_instance = None
_last_translation = None


def _test_googletrans():
    """Тестирует работоспособность googletrans"""
    try:
        from googletrans import Translator
        translator = Translator()

        result = translator.translate("hello", src='en', dest='ru')
        if result and result.text and result.text != "hello":
            print(f"Google Translate тест: 'hello' -> '{result.text}'")
            return translator
        else:
            print("Google Translate: неожиданный результат")
            return None
    except Exception as e:
        print(f"Google Translate ошибка: {e}")
        return None


# Инициализация переводчика
print("Инициализация переводчика...")

translator_instance = _test_googletrans()
if translator_instance:
    TRANSLATOR_TYPE = 'googletrans'
else:
    TRANSLATOR_TYPE = 'mock'
    print("Используется заглушка переводчика")


def translate_text(text, src_lang='en', dest_lang='ru'):
    """Основная функция перевода"""
    global _last_translation

    if not text or not text.strip():
        return ""

    try:
        if TRANSLATOR_TYPE == 'googletrans':
            result = translator_instance.translate(text, src=src_lang, dest=dest_lang)
            translated = result.text
        else:  # mock
            mock_dict = {
                'hello': 'привет',
                'hello world': 'привет мир',
                'this is a test': 'это тест',
            }
            translated = mock_dict.get(text.lower(), f"[ПЕРЕВОД: {text}]")

        _last_translation = {'original': text, 'translated': translated, 'method': TRANSLATOR_TYPE}
        return translated

    except Exception as e:
        logging.error(f"Ошибка перевода: {e}")
        return text


def get_translator_status():
    """Получить статус переводчика"""
    return {
        'type': TRANSLATOR_TYPE,
        'working': TRANSLATOR_TYPE is not None,
        'description': 'Google Translate API' if TRANSLATOR_TYPE == 'googletrans' else 'Демо-переводчик для тестирования',
        'last_translation': _last_translation
    }