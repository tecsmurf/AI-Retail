# Edge box image. Build from the repository root (it reuses backend/app/cv):
#   docker build -t purplesol-edge -f edge/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /edge

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch (avoids ~2 GB of CUDA libraries).
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 torchvision==0.20.1
COPY edge/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# The same detection, tracking and event code as the cloud worker.
COPY backend/app/__init__.py backend/app/config.py ./app/
COPY backend/app/cv ./app/cv
COPY backend/yolo11n.pt ./yolo11n.pt
COPY edge/purplesol_edge ./purplesol_edge

RUN useradd --create-home --uid 10001 edge && mkdir -p /data && chown edge /data
USER edge
ENV YOLO_MODEL=/edge/yolo11n.pt YOLO_CONFIG_DIR=/tmp/ultralytics \
    PURPLESOL_EDGE_CONFIG=/config/edge.json PURPLESOL_EDGE_STATE=/data
VOLUME ["/data"]
ENTRYPOINT ["python", "-m", "purplesol_edge"]
CMD ["run"]
