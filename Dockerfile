FROM apache/airflow:2.10.5-python3.11
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PYTHONPATH=/opt/mtg PYSPARK_PYTHON=python SPARK_LOCAL_IP=127.0.0.1
WORKDIR /opt/mtg
COPY --chown=airflow:root requirements.txt .
USER airflow
RUN pip install --no-cache-dir 'apache-airflow==2.10.5' 'pyspark==3.5.4' -r requirements.txt \
    --constraint https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.11.txt
COPY --chown=airflow:root . .
USER root
RUN mkdir -p /opt/mtg/work /opt/airflow/metadata \
    && chown airflow:root /opt/mtg /opt/mtg/work /opt/airflow/metadata
USER airflow
