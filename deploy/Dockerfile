FROM python:3.11-slim

# Node.js for the ziwei engine
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node dependencies
COPY package.json package-lock.json* ./
RUN npm install

# App code
COPY api/ api/
COPY prompts/ prompts/

EXPOSE 8119

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8119"]
