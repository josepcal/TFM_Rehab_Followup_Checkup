FROM python:3.12-slim
WORKDIR /app
RUN pip install --upgrade pip
RUN pip install --no-cache-dir uvicorn fastapi sqlalchemy alembic python-jose librosa scipy soundfile numpy
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
