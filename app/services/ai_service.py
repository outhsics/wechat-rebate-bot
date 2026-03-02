import httpx

from app.config import get_settings


class AIService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def reply(self, user_text: str) -> str:
        if not self.settings.openai_api_key:
            return (
                "我可以帮你做商品返利查询。\n"
                "请直接发京东/拼多多/淘宝商品链接，我会返回券后价和预计返利。"
            )

        try:
            return self._call_openai(user_text)
        except Exception:
            return "暂时有点忙，请稍后再试。也可以直接发商品链接，我先帮你算返利。"

    def _call_openai(self, user_text: str) -> str:
        endpoint = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是公众号客服助手。回答简洁，优先引导用户发送电商商品链接以获取返利。",
                },
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.4,
            "max_tokens": 200,
        }

        with httpx.Client(timeout=8.0) as client:
            resp = client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"].strip()
