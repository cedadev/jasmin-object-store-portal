# Jasmin Object Store Portal

A portal to manage object store access keys.

Built with fast-api.

## Setup

1. Install Poetry  
   `curl -sSL https://install.python-poetry.org | python3 -`
2. Install dependencies  
   `poetry install`
3. Install Redis. [Detailed documentation available on the redis website.](https://redis.io/docs/getting-started/installation/)
4. Create the file `conf\common.secrets.yaml`
5. Replace the placeholders in [Config structure](#config-structure)
6. Run

```bash
poetry run uvicorn objectstore_interface.main:app --reload
```

## Config structure
The file `conf\common.secrets.yaml` should look something like this:
```yaml
accounts:
  client_id: "client id"
  client_secret: "client secret"
  scope: " scope"
  redirectUri: http://127.0.0.1:8000/oauth2/redirect

projects:
  client_id: "client id"
  client_secret: "client secret"
  scope: " scope"

s3:
  auth_secret: 'auth secret'

redis:
  url: 'redis://localhost'
testing: false
```

## Add new dependencies
To add new dependencies you need to first add them with poetry as normal, then to ensure that the docker build process will pick them up run `poetry export --without-hashes --format=requirements.txt --output=requirements.txt`.