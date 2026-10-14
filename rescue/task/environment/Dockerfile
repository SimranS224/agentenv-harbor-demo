FROM python:3.12.10-alpine3.21@sha256:9c51ecce261773a684c8345b2d4673700055c513b4d54bc0719337d3e4ee552e
WORKDIR /app
ADD https://codeload.github.com/brean/python-pathfinding/tar.gz/e8d3600ace29707912f1d92b7121e3ee99b4b580 /tmp/source.tar.gz
RUN mkdir src && tar -xzf /tmp/source.tar.gz --strip-components=1 -C src && rm /tmp/source.tar.gz
COPY rescue.py /app/src/pathfinding/rescue.py
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1
CMD ["sleep", "infinity"]
