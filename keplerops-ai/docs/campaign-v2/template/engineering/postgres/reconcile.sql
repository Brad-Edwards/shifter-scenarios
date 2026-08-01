DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jupyterhub') THEN
    CREATE ROLE jupyterhub LOGIN PASSWORD 'KeplerV2-Training-JupyterHubDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'labelstudio') THEN
    CREATE ROLE labelstudio LOGIN PASSWORD 'KeplerV2-Training-LabelStudioDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lakefs') THEN
    CREATE ROLE lakefs LOGIN PASSWORD 'KeplerV2-Training-LakeFSDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mlflow') THEN
    CREATE ROLE mlflow LOGIN PASSWORD 'KeplerV2-Training-MLflowDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow') THEN
    CREATE ROLE airflow LOGIN PASSWORD 'KeplerV2-Training-AirflowDB';
  END IF;
END
$$;

ALTER ROLE jupyterhub WITH LOGIN PASSWORD 'KeplerV2-Training-JupyterHubDB';
ALTER ROLE labelstudio WITH LOGIN PASSWORD 'KeplerV2-Training-LabelStudioDB';
ALTER ROLE lakefs WITH LOGIN PASSWORD 'KeplerV2-Training-LakeFSDB';
ALTER ROLE mlflow WITH LOGIN PASSWORD 'KeplerV2-Training-MLflowDB';
ALTER ROLE airflow WITH LOGIN PASSWORD 'KeplerV2-Training-AirflowDB';

SELECT format('CREATE DATABASE %I OWNER %I', db_name, owner_name)
FROM (VALUES
  ('jupyterhub', 'jupyterhub'),
  ('labelstudio', 'labelstudio'),
  ('lakefs', 'lakefs'),
  ('mlflow', 'mlflow'),
  ('airflow', 'airflow')
) AS required(db_name, owner_name)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = db_name)
\gexec
