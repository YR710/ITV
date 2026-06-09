# 多阶段构建，减小最终镜像体积
FROM python:3.10-slim-bookworm AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.10-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目文件
COPY . .

# 创建必要目录
RUN mkdir -p /app/data /app/output

# 赋予脚本执行权限
RUN chmod +x start.sh

# 暴露HTTP端口
EXPOSE 8080

# 入口
CMD ["./start.sh"]
