#!/bin/bash
# Run the arbitrage service with websocket support

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the service
python -m services.main "$@"

