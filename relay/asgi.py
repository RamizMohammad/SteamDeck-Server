"""ASGI entrypoint: `uvicorn relay.asgi:app`"""

from .main import create_relay_app

app = create_relay_app()
