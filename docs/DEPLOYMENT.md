# 部署指南

## 1. 服务器准备
- Linux 2C2G 起步
- 已安装 Docker / Docker Compose
- 一个可用域名（HTTPS）

## 2. 配置环境变量
```bash
cp .env.example .env
# 修改以下关键项
# WECHAT_TOKEN
# ADMIN_API_KEY
# WECHAT_APP_ID
# WECHAT_APP_SECRET
# OPENAI_API_KEY
# MESSAGE_RATE_LIMIT_PER_MIN
```

## 3. 启动
```bash
docker compose up -d --build
```

## 4. 反向代理（Nginx）
将 `https://your-domain/wechat/callback` 反代到 `http://127.0.0.1:8080/wechat/callback`。

## 5. 验证
- `GET /healthz` 返回 `ok: true`
- 公众号后台服务器配置校验通过
- 微信给公众号发文本可收到回复

## 6. 生产建议
- 增加 Redis（限流、幂等）
- 增加 MySQL（订单增长后替代 SQLite）
- 管理接口统一带 `X-API-Key`，并加 Nginx IP 白名单
- 引入 Sentry/Prometheus 做监控
