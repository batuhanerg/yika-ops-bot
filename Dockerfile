FROM python:3.12-slim

WORKDIR /app

# Install build deps for python-Levenshtein (thefuzz speedup)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

CMD ["python", "-m", "app.main"]
