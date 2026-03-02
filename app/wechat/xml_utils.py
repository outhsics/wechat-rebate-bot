import time
import xml.etree.ElementTree as ET


def parse_xml_to_dict(xml_body: bytes) -> dict[str, str]:
    root = ET.fromstring(xml_body)
    payload: dict[str, str] = {}
    for child in root:
        payload[child.tag] = child.text or ""
    return payload


def build_text_response(to_user: str, from_user: str, content: str) -> str:
    safe_content = content.replace("<![CDATA[", "").replace("]]>", "")
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{safe_content}]]></Content>"
        "</xml>"
    )
