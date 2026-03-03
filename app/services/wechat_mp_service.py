from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.config import get_settings


class WeChatMPService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._access_token: Optional[str] = None
        self._token_expire_at: datetime = datetime.utcnow()

    def _fetch_access_token(self) -> Optional[str]:
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            return None

        endpoint = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.settings.wechat_app_id,
            "secret": self.settings.wechat_app_secret,
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(endpoint, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return None

        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 0))
        if not token or expires_in <= 0:
            return None

        self._access_token = token
        self._token_expire_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in - 120))
        return token

    def _get_access_token(self) -> Optional[str]:
        if self._access_token and datetime.utcnow() < self._token_expire_at:
            return self._access_token
        return self._fetch_access_token()

    def send_text(self, openid: str, text: str) -> tuple[bool, str]:
        token = self._get_access_token()
        if not token:
            return False, "missing_or_invalid_wechat_credentials"

        endpoint = "https://api.weixin.qq.com/cgi-bin/message/custom/send"
        params = {"access_token": token}
        payload = {
            "touser": openid,
            "msgtype": "text",
            "text": {"content": text},
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(endpoint, params=params, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            return False, f"http_error:{exc}"

        errcode = int(data.get("errcode", -1))
        if errcode == 0:
            return True, "ok"
        return False, f"{errcode}:{data.get('errmsg', 'unknown')}"
