FROM python:3.12.10-alpine3.21@sha256:9c51ecce261773a684c8345b2d4673700055c513b4d54bc0719337d3e4ee552e
RUN apk add --no-cache bash
WORKDIR /app
# Public source is pinned; no benchmark solutions or verifier files enter the image.
ADD https://codeload.github.com/psf/requests/tar.gz/0e322af87745eff34caffe4df68456ebc20d9068 /tmp/requests.tar.gz
RUN tar -xzf /tmp/requests.tar.gz --strip-components=1 -C /app && rm /tmp/requests.tar.gz
RUN pip install --no-cache-dir certifi==2025.1.31 charset-normalizer==3.4.1 idna==3.10 urllib3==2.3.0
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1
COPY seed.py /tmp/seed.py
RUN python /tmp/seed.py && rm /tmp/seed.py
CMD ["sleep", "infinity"]
