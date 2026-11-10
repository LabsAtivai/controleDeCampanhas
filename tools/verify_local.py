"""Checks the running local installation using its private bootstrap credentials."""
from pathlib import Path
import json

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = dotenv_values(ROOT / '.env')
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=90) as client:
        assert client.get('/api/ready').status_code == 200
        response = client.post('/api/auth/login', json={
            'email': values['ADMIN_EMAIL'], 'password': values['ADMIN_PASSWORD']})
        assert response.status_code == 200
        assert response.json()['email'] == values['ADMIN_EMAIL']
        result = {'ready': True, 'login': True}
        for path in ['/dados.html', '/analise.html', '/index.html', '/equipe.html', '/api/users', '/api/jobs']:
            result[path] = client.get(path).status_code == 200
        assert all(result.values())
        print(json.dumps(result))


if __name__ == '__main__':
    main()
