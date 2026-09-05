FROM python:3.11-slim

WORKDIR /app/designer_agent

# Install dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend source
COPY backend/ ./backend/

WORKDIR /app/designer_agent/backend

EXPOSE 8282

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8282"]

