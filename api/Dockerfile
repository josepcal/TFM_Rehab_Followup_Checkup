FROM python:3.12-slim
WORKDIR /app
# Install from requirements.txt so declared deps (parselmouth, psycopg2, boto3, …)
# are not silently dropped by a hand-maintained package list.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
