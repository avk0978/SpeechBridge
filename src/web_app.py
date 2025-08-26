#!/usr/bin/env python3
"""
Flask веб-приложение для Video-Translator
Веб-интерфейс для загрузки и перевода видео
"""

import time
import uuid
import threading
from pathlib import Path
from typing import Dict, Optional

from flask import Flask, request, render_template, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Локальные модули
from config import config
from video_translator import VideoTranslator


class TranslationTask:
    """Модель задачи перевода"""

    def __init__(self, task_id: str, input_file: str, original_filename: str = ""):
        self.task_id = task_id
        self.input_file = input_file
        self.original_filename = original_filename
        self.status = 'pending'  # pending, processing, completed, error
        self.progress = 0
        self.current_stage = 'Инициализация'
        self.output_file: Optional[str] = None
        self.error_message: Optional[str] = None
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.file_info: Dict = {}

    def to_dict(self) -> Dict:
        """Преобразование в словарь для JSON ответа"""
        data = {
            'task_id': self.task_id,
            'status': self.status,
            'progress': self.progress,
            'current_stage': self.current_stage,
            'elapsed_time': int(time.time() - self.start_time),
            'original_filename': self.original_filename,
            'file_info': self.file_info
        }

        if self.status == 'completed':
            data['output_file'] = self.output_file
            if self.end_time:
                data['total_time'] = int(self.end_time - self.start_time)
        elif self.status == 'error':
            data['error_message'] = self.error_message

        return data


class VideoTranslatorApp:
    """Flask приложение для Video-Translator"""

    def __init__(self):
        self.app = Flask(__name__,
                         template_folder=str(config.TEMPLATES_FOLDER),
                         static_folder=str(config.STATIC_FOLDER))
        self.config = config
        self.setup_app()
        self.video_translator = VideoTranslator()
        self.active_tasks: Dict[str, TranslationTask] = {}
        self.setup_routes()

        print(f"Flask приложение инициализировано")
        print(f"Templates: {config.TEMPLATES_FOLDER}")
        print(f"Static: {config.STATIC_FOLDER}")

    def setup_app(self):
        """Настройка Flask приложения"""
        self.app.config.update(
            SECRET_KEY=self.config.SECRET_KEY,
            MAX_CONTENT_LENGTH=self.config.MAX_CONTENT_LENGTH,
            UPLOAD_FOLDER=str(self.config.UPLOAD_FOLDER),
            OUTPUT_FOLDER=str(self.config.OUTPUT_FOLDER)
        )
        CORS(self.app)

    def setup_routes(self):
        """Настройка маршрутов"""

        @self.app.route('/')
        def index():
            """Главная страница"""
            translator_status = self.video_translator.get_translator_status()
            return render_template('index.html',
                                   max_file_size=self.config.MAX_FILE_SIZE_MB,
                                   allowed_extensions=list(self.config.ALLOWED_EXTENSIONS),
                                   translator_status=translator_status)

        @self.app.route('/api/upload', methods=['POST'])
        def upload_video():
            """Загрузка и обработка видео"""
            try:
                # Проверка наличия файла
                if 'video' not in request.files:
                    return jsonify({'error': 'Файл не найден в запросе'}), 400

                file = request.files['video']
                if file.filename == '':
                    return jsonify({'error': 'Файл не выбран'}), 400

                # Валидация имени файла
                if not self.config.is_allowed_file(file.filename):
                    return jsonify({
                        'error': f'Неподдерживаемый формат файла. Разрешены: {", ".join(self.config.ALLOWED_EXTENSIONS)}'
                    }), 400

                # Генерация ID задачи и безопасного имени файла
                task_id = str(uuid.uuid4())
                original_filename = file.filename
                safe_filename = secure_filename(file.filename)

                # Создание уникального имени файла
                file_extension = Path(safe_filename).suffix
                unique_filename = f"{task_id}_{safe_filename}"
                input_path = self.config.UPLOAD_FOLDER / unique_filename

                # Сохранение файла
                file.save(str(input_path))

                # Валидация загруженного файла
                validation = self.video_translator.validate_video_file(str(input_path))
                if not validation['valid']:
                    # Удаляем невалидный файл
                    input_path.unlink(missing_ok=True)
                    return jsonify({
                        'error': 'Ошибка валидации файла',
                        'details': validation['errors']
                    }), 400

                # Создание задачи
                task = TranslationTask(task_id, str(input_path), original_filename)
                task.file_info = validation['info']
                self.active_tasks[task_id] = task

                # Запуск обработки в отдельном потоке
                thread = threading.Thread(target=self.process_video_async, args=(task,))
                thread.daemon = True
                thread.start()

                return jsonify({
                    'task_id': task_id,
                    'status': 'uploaded',
                    'message': 'Файл загружен, начинается обработка',
                    'file_info': validation['info']
                })

            except Exception as e:
                self.app.logger.error(f"Ошибка загрузки файла: {e}")
                return jsonify({'error': f'Ошибка загрузки: {str(e)}'}), 500

        @self.app.route('/api/status/<task_id>')
        def get_status(task_id):
            """Получение статуса задачи"""
            if task_id not in self.active_tasks:
                return jsonify({'error': 'Задача не найдена'}), 404

            task = self.active_tasks[task_id]
            return jsonify(task.to_dict())

        @self.app.route('/api/download/<task_id>')
        def download_result(task_id):
            """Скачивание результата"""
            if task_id not in self.active_tasks:
                return jsonify({'error': 'Задача не найдена'}), 404

            task = self.active_tasks[task_id]

            if task.status != 'completed' or not task.output_file:
                return jsonify({'error': 'Файл не готов к скачиванию'}), 400

            output_path = Path(task.output_file)
            if not output_path.exists():
                return jsonify({'error': 'Файл результата не найден'}), 404

            # Генерируем имя для скачивания
            original_name = Path(task.original_filename).stem
            download_name = f'{original_name}_translated.mp4'

            return send_file(
                str(output_path),
                as_attachment=True,
                download_name=download_name,
                mimetype='video/mp4'
            )

        @self.app.route('/api/tasks')
        def list_tasks():
            """Получение списка всех задач"""
            tasks_data = {}
            for task_id, task in self.active_tasks.items():
                tasks_data[task_id] = task.to_dict()

            return jsonify({
                'total_tasks': len(tasks_data),
                'tasks': tasks_data
            })

        @self.app.route('/api/delete/<task_id>', methods=['DELETE'])
        def delete_task(task_id):
            """Удаление задачи и связанных файлов"""
            if task_id not in self.active_tasks:
                return jsonify({'error': 'Задача не найдена'}), 404

            task = self.active_tasks[task_id]

            # Можно удалять только завершенные или ошибочные задачи
            if task.status in ['processing']:
                return jsonify({'error': 'Нельзя удалить задачу в процессе обработки'}), 400

            try:
                # Удаление файлов
                if task.input_file and Path(task.input_file).exists():
                    Path(task.input_file).unlink()

                if task.output_file and Path(task.output_file).exists():
                    Path(task.output_file).unlink()

                # Удаление из памяти
                del self.active_tasks[task_id]

                return jsonify({'message': 'Задача удалена'})

            except Exception as e:
                self.app.logger.error(f"Ошибка удаления задачи {task_id}: {e}")
                return jsonify({'error': 'Ошибка удаления задачи'}), 500

        @self.app.route('/api/translator/status')
        def translator_status():
            """Получение статуса переводчика"""
            status = self.video_translator.get_translator_status()
            return jsonify(status)

        @self.app.route('/health')
        def health_check():
            """Проверка здоровья приложения"""
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'active_tasks': len(self.active_tasks),
                'translator': self.video_translator.get_translator_status()['type']
            })

        # Обработчики ошибок
        @self.app.errorhandler(413)
        def file_too_large(e):
            return jsonify({
                'error': f'Файл слишком большой. Максимальный размер: {self.config.MAX_FILE_SIZE_MB}MB'
            }), 413

        @self.app.errorhandler(404)
        def not_found(e):
            return jsonify({'error': 'Страница не найдена'}), 404

        @self.app.errorhandler(500)
        def internal_error(e):
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500

    def process_video_async(self, task: TranslationTask):
        """Асинхронная обработка видео"""
        try:
            task.status = 'processing'
            self.app.logger.info(f"Начало обработки задачи {task.task_id}")

            # Определение выходного файла
            output_filename = f"translated_{task.task_id}.mp4"
            output_path = self.config.OUTPUT_FOLDER / output_filename
            task.output_file = str(output_path)

            # Функция обновления прогресса
            def update_progress(stage: str, progress: int):
                task.current_stage = stage
                task.progress = progress
                self.app.logger.debug(f"Задача {task.task_id}: {stage} ({progress}%)")

            # Запуск перевода
            success = self.video_translator.translate_video(
                video_path=task.input_file,
                output_path=str(output_path),
                progress_callback=update_progress
            )

            if success:
                task.status = 'completed'
                task.progress = 100
                task.current_stage = 'Готово'
                self.app.logger.info(f"Задача {task.task_id} завершена успешно")
            else:
                task.status = 'error'
                task.error_message = 'Ошибка при обработке видео'
                self.app.logger.error(f"Задача {task.task_id} завершена с ошибкой")

            task.end_time = time.time()

        except Exception as e:
            task.status = 'error'
            task.error_message = str(e)
            task.end_time = time.time()
            self.app.logger.error(f"Критическая ошибка в задаче {task.task_id}: {e}")

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Очистка старых задач"""
        current_time = time.time()
        tasks_to_remove = []

        for task_id, task in self.active_tasks.items():
            if task.status in ['completed', 'error']:
                age_hours = (current_time - task.start_time) / 3600
                if age_hours > max_age_hours:
                    tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            try:
                task = self.active_tasks[task_id]
                # Удаление файлов
                if task.input_file and Path(task.input_file).exists():
                    Path(task.input_file).unlink()
                if task.output_file and Path(task.output_file).exists():
                    Path(task.output_file).unlink()
                # Удаление из памяти
                del self.active_tasks[task_id]
                self.app.logger.info(f"Очищена старая задача {task_id}")
            except Exception as e:
                self.app.logger.error(f"Ошибка очистки задачи {task_id}: {e}")

    def get_app(self) -> Flask:
        """Получение экземпляра Flask приложения"""
        return self.app

    def run(self, host: str = '127.0.0.1', port: int = 5000, debug: bool = True):
        """Запуск приложения"""
        self.app.logger.info(f"Запуск Video-Translator на {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)


def create_app() -> Flask:
    """Фабрика приложений Flask"""
    app_instance = VideoTranslatorApp()
    return app_instance.get_app()


if __name__ == "__main__":
    print("=== Тестирование Flask приложения ===")

    app = VideoTranslatorApp()
    print(f"Приложение создано")
    print(f"Активных задач: {len(app.active_tasks)}")
    print(f"Конфигурация загружена: {app.config}")

    # Тестовый запуск
    print("Запуск тестового сервера...")
    app.run(debug=True)