FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 HF_HOME=/weights HF_ENDPOINT=https://hf-mirror.com
WORKDIR /srv

COPY pyproject.toml ./
COPY app ./app
COPY pipeline ./pipeline
COPY rules ./rules
COPY scripts ./scripts
COPY prototypes ./prototypes
COPY config.yml ./

RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -e .

# Bake the weights into the image so the container never needs internet access.
RUN python scripts/download_weights.py && echo "weights ready"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
