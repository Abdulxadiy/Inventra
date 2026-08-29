import multiprocessing
import os

# Monkey-patch gevent FIRST, before any imports that might use threading
if os.environ.get("GUNICORN_WORKER_CLASS", "gevent") == "gevent":
    from gevent import monkey
    monkey.patch_all()

bind = "0.0.0.0:8000"

workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gevent")

worker_connections = 1000

timeout = 30

graceful_timeout = 30

max_requests = 1000

max_requests_jitter = 100

accesslog = "-"
errorlog = "-"

access_log_format = '%(h)s "%(r)s" %(s)s %(D)sus'

loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

preload_app = False  # gevent worker gives DatabaseError when True — checked, don't change

# For gevent: use ares resolver instead of thread-based resolver
if worker_class == "gevent":
    os.environ["GEVENT_RESOLVER"] = "ares"

proc_name = "inventra_gunicorn"
