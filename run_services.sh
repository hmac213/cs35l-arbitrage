#!/bin/bash
# Run the arbitrage service with websocket support

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the service with DEBUG logging enabled
# To use INFO level instead, remove --debug or use --log-level INFO
python -m services.main --log-level INFO "$@"

