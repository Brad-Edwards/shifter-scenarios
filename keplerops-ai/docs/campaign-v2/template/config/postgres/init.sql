CREATE ROLE keycloak LOGIN PASSWORD 'KeplerV2-Training-KeycloakDB';
CREATE DATABASE keycloak OWNER keycloak;

CREATE ROLE forgejo LOGIN PASSWORD 'KeplerV2-Training-ForgejoDB';
CREATE DATABASE forgejo OWNER forgejo;

CREATE ROLE redmine LOGIN PASSWORD 'KeplerV2-Training-RedmineDB';
CREATE DATABASE redmine OWNER redmine;

CREATE ROLE nextcloud LOGIN PASSWORD 'KeplerV2-Training-NextcloudDB';
CREATE DATABASE nextcloud OWNER nextcloud;

CREATE ROLE zammad LOGIN PASSWORD 'KeplerV2-Training-ZammadDB';
CREATE DATABASE zammad OWNER zammad;

CREATE ROLE mlflow LOGIN PASSWORD 'KeplerV2-Training-MLflowDB';
CREATE DATABASE mlflow OWNER mlflow;

CREATE ROLE airflow LOGIN PASSWORD 'KeplerV2-Training-AirflowDB';
CREATE DATABASE airflow OWNER airflow;

CREATE ROLE langflow LOGIN PASSWORD 'KeplerV2-Training-LangflowDB';
CREATE DATABASE langflow OWNER langflow;

CREATE ROLE business LOGIN PASSWORD 'KeplerV2-Training-BusinessDB';
CREATE DATABASE business OWNER business;
