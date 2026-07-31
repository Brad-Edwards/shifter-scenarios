ARG BASE_IMAGE=apache/airflow@sha256:235a362ae98882d21c9f6bfa0b9cdd5da8f36c94b5d58c397cf7a9674509be35
FROM ${BASE_IMAGE}

RUN python -m pip install --no-cache-dir \
    mlflow-skinny==3.3.2 \
    'psycopg[binary]==3.2.10' \
    scikit-learn==1.7.1
COPY assets/workflows/keplerops_distillation.py /opt/airflow/dags/keplerops_distillation.py
COPY assets/workflows/research_content.py /opt/airflow/dags/research_content.py
COPY assets/workflows/training_model.py /opt/airflow/dags/training_model.py
COPY assets/workflows/company_state_workflow.py /opt/airflow/dags/company_state_workflow.py
COPY assets/services/keplerops-runtime/training_poisoning.py /opt/airflow/dags/training_poisoning.py
COPY assets/services/keplerops-runtime/model_extraction.py /opt/airflow/dags/model_extraction.py
COPY assets/content/datasets/distillation.jsonl /opt/keplerops/baseline/distillation.jsonl
COPY assets/content/company-state/company-state.yaml /opt/keplerops/company-state.yaml
COPY assets/workflows/company_airflow_adapter.py /opt/keplerops/company_airflow_adapter.py
COPY assets/workflows/company-airflow-entrypoint.sh /usr/local/bin/company-airflow-entrypoint
COPY assets/oracle/model-extraction.json /opt/keplerops/oracle/model-extraction.json
COPY --chown=50000:0 assets/content/credentials/airflow-passwords.json /opt/keplerops/airflow-passwords.json
USER root
RUN install -d -o 50000 -g 0 -m 0750 /opt/keplerops/output \
    && chmod 0755 /usr/local/bin/company-airflow-entrypoint
USER 50000:0
ENTRYPOINT ["/usr/local/bin/company-airflow-entrypoint"]
