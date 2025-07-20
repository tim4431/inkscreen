FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# 先复制requirements.txt并安装依赖（利用Docker缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# 创建挂载点目录
RUN mkdir -p output assets

CMD ["python", "main.py"]
