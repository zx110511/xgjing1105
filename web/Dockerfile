# === Stage 1: Build ===
FROM node:20-alpine AS builder

WORKDIR /app

# 安装依赖
COPY package.json package-lock.json* ./
RUN npm ci --production=false

# 构建参数
ARG VITE_API_BASE_URL=http://localhost:8778
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# 复制源码并构建
COPY . .
RUN npm run build

# === Stage 2: Nginx ===
FROM nginx:alpine AS runtime

LABEL maintainer="tianji-team" \
    description="天机 Web UI"

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx配置：反向代理API到后端
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
