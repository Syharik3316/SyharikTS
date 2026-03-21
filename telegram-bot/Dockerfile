FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefer-binary --timeout 1200 --retries 10 -r requirements.txt

COPY . .

CMD ["python", "main.py"]
