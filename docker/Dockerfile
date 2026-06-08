FROM python:3.10-slim-bookworm

# 设置工作目录
WORKDIR /app

# 换用国内可用的镜像源（优先使用阿里云，备选清华）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    || ( sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list \
        && sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list )

# 安装系统依赖：ffmpeg、wget
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用清华镜像加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目文件
COPY . .

# 创建数据目录（持久化）
RUN mkdir -p /app/data /app/output

# 赋予 start.sh 执行权限
RUN chmod +x start.sh

# 设置环境变量（可被 docker-compose 覆盖）
ENV PYTHONUNBUFFERED=1 \
    MAX_WORKERS=10 \
    TIMEOUT=10 \
    FFMPEG_ENABLE=true \
    ENABLE_RETRY=true \
    ENABLE_IP_RESOLVE=true \
    ENABLE_REGION_FILTER=false \
    PREFERRED_LOCATION="" \
    PREFERRED_ISP="" \
    CACHE_SPEED_HOURS=24 \
    CACHE_RAW_HOURS=24 \
    MAX_SOURCES_PER_CHANNEL=5 \
    DEMO_MATCH_MODE=contains \
    ENABLE_DEMO_FILTER=true \
    ENABLE_ALIAS=true \
    ENABLE_BLACKLIST=true \
    DATABASE_ENABLE=true \
    ENABLE_WEB_SERVER=true \
    WEB_SERVER_PORT=8000 \
    WEB_SERVER_HOST=0.0.0.0 \
    RUN_MODE=schedule \
    SCHEDULE_INTERVAL=21600

# 暴露 HTTP 端口
EXPOSE 8000

# 使用自定义启动脚本
ENTRYPOINT ["./start.sh"]
