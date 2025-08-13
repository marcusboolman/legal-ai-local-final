# api/tasks/celery_app.py
from celery import Celery
import os
redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
cel = Celery("legal_tasks", broker=redis_url, backend=redis_url)
cel.conf.update(task_serializer='json', result_serializer='json', accept_content=['json'])
