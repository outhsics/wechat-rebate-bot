import logging

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.admin import router as admin_router
from app.config import get_settings
from app.database import Base, engine, get_db
from app.services.message_service import MessageService
from app.wechat.signature import verify_wechat_signature
from app.wechat.xml_utils import build_text_response, parse_xml_to_dict

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.include_router(admin_router)
message_service = MessageService()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("database initialized")


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": settings.app_name}


@app.get("/wechat/callback")
def wechat_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(""),
):
    if not verify_wechat_signature(settings.wechat_token, signature, timestamp, nonce):
        raise HTTPException(status_code=401, detail="invalid signature")
    return PlainTextResponse(echostr)


@app.post("/wechat/callback")
async def wechat_callback(
    request: Request,
    db: Session = Depends(get_db),
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    if not verify_wechat_signature(settings.wechat_token, signature, timestamp, nonce):
        raise HTTPException(status_code=401, detail="invalid signature")

    body = await request.body()
    payload = parse_xml_to_dict(body)
    logger.info("incoming message type=%s from=%s", payload.get("MsgType"), payload.get("FromUserName"))

    reply_text = message_service.handle_message(db, payload)
    if not reply_text:
        return PlainTextResponse("success")

    response_xml = build_text_response(
        to_user=payload.get("FromUserName", ""),
        from_user=payload.get("ToUserName", ""),
        content=reply_text,
    )
    return Response(content=response_xml, media_type="application/xml")
