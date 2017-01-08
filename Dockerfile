FROM cybe/ps-python:alpine35

COPY plugin /plugin

ENTRYPOINT ["python", "/plugin/trigger.py"]
