"""Compatibility entrypoint; use python -m waitress --call webapp:create_app."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import create_app
app = create_app()
if __name__ == '__main__':
    import os
    from waitress import serve
    serve(app, host='127.0.0.1', port=int(os.getenv('PORT', '8000')), threads=8)
