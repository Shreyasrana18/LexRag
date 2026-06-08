from arq.connections import RedisSettings
from app.worker.tasks import process_upload

class WorkerSettings:
    functions = [process_upload]
    redis_settings = RedisSettings(host="localhost", port=6379)
    max_jobs = 10
    job_timeout = 3600  