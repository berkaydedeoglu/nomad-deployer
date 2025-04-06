FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN curl -Lo /tmp/nomad.zip https://releases.hashicorp.com/nomad/1.9.7/nomad_1.9.7_linux_amd64.zip && \
    unzip /tmp/nomad.zip -d ./ && \
    chmod +x ./nomad && \
    rm /tmp/nomad.zip

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
