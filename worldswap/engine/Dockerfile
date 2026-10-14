FROM python:3.12-slim
RUN pip install --no-cache-dir pymunk==7.3.0
WORKDIR /app
COPY simulate.py /app/simulate.py
COPY controller.py /app/src/controller.py
CMD ["sleep", "infinity"]
