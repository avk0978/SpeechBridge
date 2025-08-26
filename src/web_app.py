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
            """Получ