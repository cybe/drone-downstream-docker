FROM python:3.5-alpine

COPY plugin /plugin

ENTRYPOINT ["python", "/plugin/trigger.py"]
