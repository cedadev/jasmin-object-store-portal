# Jasmin Object Store Portal
A portal to manage object store access keys.

Built with fast-api.

## Setup
1. Install Poetry  
`curl -sSL https://install.python-poetry.org | python3 -`
2. Install dependencies  
`poetry install`
3. Create a .env file in `objectstore_interface`  
4. Add your jasmin accounts portal `client_id` and `client_secret` as well as your `scope`
5. Add your jasmin projects portal `client_id` and `client_secret` as well as your `scope`
6. Run  
```bash
cd objectstore_interface/
poetry run uvicorn main:app --reload
```