DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
    CREATE ROLE keycloak LOGIN PASSWORD 'KeplerV2-Training-KeycloakDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'forgejo') THEN
    CREATE ROLE forgejo LOGIN PASSWORD 'KeplerV2-Training-ForgejoDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'redmine') THEN
    CREATE ROLE redmine LOGIN PASSWORD 'KeplerV2-Training-RedmineDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nextcloud') THEN
    CREATE ROLE nextcloud LOGIN PASSWORD 'KeplerV2-Training-NextcloudDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'zammad') THEN
    CREATE ROLE zammad LOGIN PASSWORD 'KeplerV2-Training-ZammadDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mlflow') THEN
    CREATE ROLE mlflow LOGIN PASSWORD 'KeplerV2-Training-MLflowDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow') THEN
    CREATE ROLE airflow LOGIN PASSWORD 'KeplerV2-Training-AirflowDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'langflow') THEN
    CREATE ROLE langflow LOGIN PASSWORD 'KeplerV2-Training-LangflowDB';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'business') THEN
    CREATE ROLE business LOGIN PASSWORD 'KeplerV2-Training-BusinessDB';
  END IF;
END
$$;

ALTER ROLE keycloak WITH LOGIN PASSWORD 'KeplerV2-Training-KeycloakDB';
ALTER ROLE forgejo WITH LOGIN PASSWORD 'KeplerV2-Training-ForgejoDB';
ALTER ROLE redmine WITH LOGIN PASSWORD 'KeplerV2-Training-RedmineDB';
ALTER ROLE nextcloud WITH LOGIN PASSWORD 'KeplerV2-Training-NextcloudDB';
ALTER ROLE zammad WITH LOGIN PASSWORD 'KeplerV2-Training-ZammadDB';
ALTER ROLE mlflow WITH LOGIN PASSWORD 'KeplerV2-Training-MLflowDB';
ALTER ROLE airflow WITH LOGIN PASSWORD 'KeplerV2-Training-AirflowDB';
ALTER ROLE langflow WITH LOGIN PASSWORD 'KeplerV2-Training-LangflowDB';
ALTER ROLE business WITH LOGIN PASSWORD 'KeplerV2-Training-BusinessDB';

SELECT format('CREATE DATABASE %I OWNER %I', db_name, owner_name)
FROM (VALUES
  ('keycloak', 'keycloak'),
  ('forgejo', 'forgejo'),
  ('redmine', 'redmine'),
  ('nextcloud', 'nextcloud'),
  ('zammad', 'zammad'),
  ('mlflow', 'mlflow'),
  ('airflow', 'airflow'),
  ('langflow', 'langflow'),
  ('business', 'business')
) AS required(db_name, owner_name)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = db_name)
\gexec
