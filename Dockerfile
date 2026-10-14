FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY satanabe_builder/ ./satanabe_builder/
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data
CMD ["python", "-m", "satanabe_builder.bot"]
