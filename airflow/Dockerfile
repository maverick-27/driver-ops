# Airflow 2.10.3 on Python 3.12, LocalExecutor. Separate from the API image: it carries Docling for PDF parsing.
FROM python:3.12-slim-bookworm

ARG AIRFLOW_VERSION=2.10.3
ENV AIRFLOW_HOME=/opt/airflow PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpq5 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "apache-airflow[postgres]==${AIRFLOW_VERSION}" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"

# Only what the DAG imports need. Airflow and its SQLAlchemy line are pinned again so this step cannot move them.
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install "apache-airflow==${AIRFLOW_VERSION}" "sqlalchemy<2" -r /tmp/requirements-airflow.txt

RUN useradd --uid 50000 --create-home --home-dir /home/airflow airflow \
    && mkdir -p /opt/airflow/dags /opt/airflow/logs /home/airflow/.cache \
    && chown -R airflow:airflow /opt/airflow /home/airflow
COPY --chown=airflow:airflow entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER airflow
WORKDIR /opt/airflow
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
