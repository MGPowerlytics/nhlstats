FROM apache/airflow:3.1.6

COPY requirements.txt /requirements.txt
COPY requirements_dashboard.txt /requirements_dashboard.txt
RUN pip install --no-cache-dir -r /requirements.txt && pip install --no-cache-dir -r /requirements_dashboard.txt
