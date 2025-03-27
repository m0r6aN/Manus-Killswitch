FROM python:3.12-slim

WORKDIR /app

# Copy the backend structure
COPY backend/shared_models /app/backend/shared_models
COPY backend/websocket_streaming/main.py /app/
COPY backend/websocket_streaming/requirements.txt /app/

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose WebSocket port
EXPOSE 8000

# Run the WebSocket server
CMD ["python", "main.py"]