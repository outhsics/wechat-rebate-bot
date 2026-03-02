# wechat-rebate-bot

面向个人公众号的 AI 问答 + 电商返利机器人（可直接运行的 MVP）。

## 能力
- 公众号消息回调（签名校验 + XML 收发）
- 识别商品链接（京东/拼多多/淘宝）
- 返回券后价、预计佣金、预计返利、返利码
- 非商品消息走 AI 客服回复（支持 OpenAI）
- SQLite 数据落库（用户、链接日志、订单）
- 管理接口（查看用户、日志、订单；模拟结算）

## 目录
- `app/main.py`：入口与公众号回调
- `app/services/message_service.py`：消息分发
- `app/services/parser.py`：链接识别
- `app/services/affiliate/*`：平台适配器（京东支持真实接口调用，拼多多/淘宝为 mock）
- `app/services/ai_service.py`：AI 问答
- `app/api/admin.py`：管理 API
- `docs/DEPLOYMENT.md`：生产部署

## 快速开始
```bash
cd wechat-rebate-bot
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

健康检查：
```bash
curl http://127.0.0.1:8080/healthz
```

## 公众号接入步骤
1. 打开公众号后台 -> 开发 -> 基本配置 -> 服务器配置。
2. URL 填：`https://你的域名/wechat/callback`
3. Token 填你在 `.env` 里的 `WECHAT_TOKEN`（必须一致）。
4. EncodingAESKey 如使用明文可先不填；后续上生产建议配置安全模式。
5. 提交后微信会发起 GET 校验，服务会回传 `echostr`。

## 环境变量
- `WECHAT_TOKEN`：公众号服务器配置 Token
- `WECHAT_APP_ID/WECHAT_APP_SECRET`：后续如需客服异步消息与用户信息可用
- `OPENAI_API_KEY`：AI 问答（不填则使用内置兜底回复）
- `REBATE_RATE`：返利比例（默认 0.7）
- `JD_AFFILIATE_APP_KEY/JD_AFFILIATE_APP_SECRET`：京东联盟开放平台凭证
- `JD_AFFILIATE_ACCESS_TOKEN`：可选，部分账号需要
- `JD_AFFILIATE_API_URL`：默认 `https://api.jd.com/routerjson`
- `JD_AFFILIATE_METHOD`：默认 `jd.union.open.goods.jingfen.query`
- `JD_AFFILIATE_ELITE_ID`：默认 `1`

## 管理接口
- `GET /api/users`
- `GET /api/link-logs`
- `GET /api/orders`
- `POST /api/orders/mock-confirm`

示例：
```bash
curl -X POST http://127.0.0.1:8080/api/orders/mock-confirm \
  -H 'Content-Type: application/json' \
  -d '{
    "openid":"o_user_xxx",
    "platform":"jd",
    "product_id":"100012043978",
    "order_amount":199,
    "commission_amount":15.5
  }'
```

## 真实返利闭环怎么接
当前行为：
- 京东：优先走真实联盟 API，失败自动回退到 mock。
- 拼多多、淘宝：当前为 mock，实现文件如下：
- `app/services/affiliate/pdd.py`
- `app/services/affiliate/taobao.py`

接入真实联盟 API 后，建议流程：
1. 用户发链接 -> 解析商品 ID
2. 联盟 API 查券和佣金 -> 生成推广链接
3. 用户下单 -> 你收到订单回传（Webhook/拉单）
4. 订单状态变更为 `settled` -> 进入可返利
5. 人工或自动发放返利（微信红包/转账）

## 合规与风控建议
- 仅使用公众号官方消息能力，不接个人号自动化。
- 明确提示“返利金额以联盟结算为准”。
- 做防刷限制：同用户单位时间查询阈值。
- 保留订单与返利日志，便于申诉和对账。

## 测试
```bash
pytest -q
```

## GitHub 发布
```bash
git init
git add .
git commit -m "feat: initial wechat rebate bot mvp"
gh repo create wechat-rebate-bot --private --source . --remote origin --push
```
