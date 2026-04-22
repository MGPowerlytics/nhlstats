FROM apache/airflow:3.1.6

USER root
RUN mkdir -p /opt/airflow/{config,dags,plugins,lib,dashboard,data,logs,scripts,migrations}
USER airflow

COPY --chown=airflow:root requirements.txt /tmp/requirements.txt
COPY --chown=airflow:root requirements_dashboard.txt /tmp/requirements_dashboard.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements_dashboard.txt \
    && rm -f /tmp/requirements.txt /tmp/requirements_dashboard.txt

COPY --chown=airflow:root config /opt/airflow/config
COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root plugins /opt/airflow/plugins
COPY --chown=airflow:root lib /opt/airflow/lib
COPY --chown=airflow:root dashboard /opt/airflow/dashboard
COPY --chown=airflow:root migrations /opt/airflow/migrations
COPY --chown=airflow:root scripts /opt/airflow/scripts

ENV PYTHONPATH=/opt/airflow/plugins:/opt/airflow
WORKDIR /opt/airflow
