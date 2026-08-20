FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY public ./public
EXPOSE 5003
CMD ["python", "app.py"]
