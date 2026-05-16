"""WhatsApp webhook — receives GM messages and images, replies with campaign memory.

Supports two providers:
- Twilio WhatsApp Sandbox (easy dev setup)
- Meta Cloud API (production)

Set WHATSAPP_PROVIDER=twilio or meta in your .env.
"""
from __future__ import annotations
import base64
import os
from pathlib import Path
from typing import Optional

import requests
from flask import Flask, request, Response

from loremind.engine.tinm_adapter import CampaignStore
from loremind.processor import SessionProcessor
from loremind.schema import SessionDump
from loremind.whatsapp.vision import extract_text_from_image


app = Flask(__name__)


def _get_store() -> CampaignStore:
    campaign = os.environ.get("LOREMIND_CAMPAIGN", "default")
    return CampaignStore(campaign)


def _reply_twilio(to: str, body: str) -> None:
    from twilio.rest import Client
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.messages.create(
        from_=f"whatsapp:{os.environ['TWILIO_WHATSAPP_NUMBER']}",
        to=f"whatsapp:{to}",
        body=body,
    )


def _reply_meta(to: str, body: str) -> None:
    token = os.environ["META_WHATSAPP_TOKEN"]
    phone_id = os.environ["META_PHONE_NUMBER_ID"]
    requests.post(
        f"https://graph.facebook.com/v18.0/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        },
        timeout=10,
    )


def send_reply(to: str, body: str) -> None:
    provider = os.environ.get("WHATSAPP_PROVIDER", "twilio")
    if provider == "meta":
        _reply_meta(to, body)
    else:
        _reply_twilio(to, body)


@app.route("/webhook/twilio", methods=["POST"])
def twilio_webhook():
    """Twilio WhatsApp webhook."""
    from_number = request.form.get("From", "").replace("whatsapp:", "")
    body = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", 0))

    store = _get_store()
    processor = SessionProcessor(store)

    # Image received — OCR handwritten notes
    if num_media > 0:
        media_url = request.form.get("MediaUrl0", "")
        media_type = request.form.get("MediaContentType0", "")
        image_text = _handle_image(media_url, media_type)
        if image_text:
            dump = SessionDump(
                session_number=_current_session(store),
                raw_text=image_text,
                source="whatsapp",
            )
            entities = processor.process(dump)
            names = [e.name for e in entities]
            reply = f"Got it. Stored: {', '.join(names)}." if names else "Processed — no new entities found."
        else:
            reply = "Couldn't read the image. Try a clearer photo with better lighting."
        send_reply(from_number, reply)
        return Response("OK", status=200)

    # Text message — query or session dump
    if body:
        reply = _handle_text(body, store, processor)
        send_reply(from_number, reply)

    return Response("OK", status=200)


@app.route("/webhook/meta", methods=["GET", "POST"])
def meta_webhook():
    """Meta Cloud API webhook."""
    if request.method == "GET":
        # Verification challenge
        if request.args.get("hub.verify_token") == os.environ.get("META_VERIFY_TOKEN"):
            return request.args.get("hub.challenge", "")
        return Response("Forbidden", status=403)

    data = request.json or {}
    store = _get_store()
    processor = SessionProcessor(store)

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                from_number = msg.get("from", "")
                msg_type = msg.get("type", "text")

                if msg_type == "image":
                    image_id = msg["image"]["id"]
                    media_url = _get_meta_media_url(image_id)
                    image_text = _handle_image(media_url, "image/jpeg")
                    if image_text:
                        dump = SessionDump(
                            session_number=_current_session(store),
                            raw_text=image_text,
                            source="whatsapp",
                        )
                        entities = processor.process(dump)
                        names = [e.name for e in entities]
                        reply = f"Stored: {', '.join(names)}." if names else "No new entities found."
                    else:
                        reply = "Couldn't read the image."
                    send_reply(from_number, reply)

                elif msg_type == "text":
                    body = msg["text"]["body"]
                    reply = _handle_text(body, store, processor)
                    send_reply(from_number, reply)

    return Response("OK", status=200)


def _handle_text(body: str, store: CampaignStore, processor: SessionProcessor) -> str:
    body_lower = body.lower().strip()

    # Campaign context query
    if any(kw in body_lower for kw in ["who is", "what is", "where is", "tell me about", "?"]):
        return _query_campaign(body, store)

    # Explicit dump command
    if body_lower.startswith("save:") or body_lower.startswith("notes:"):
        notes = body[body.index(":") + 1:].strip()
        dump = SessionDump(
            session_number=_current_session(store),
            raw_text=notes,
            source="whatsapp",
        )
        entities = processor.process(dump)
        names = [e.name for e in entities]
        return f"Saved. Entities: {', '.join(names)}." if names else "Saved — no entities extracted."

    # Treat long messages as session notes
    if len(body) > 80:
        dump = SessionDump(
            session_number=_current_session(store),
            raw_text=body,
            source="whatsapp",
        )
        entities = processor.process(dump)
        names = [e.name for e in entities]
        return f"Processed. Found: {', '.join(names)}." if names else "Processed — nothing new to store."

    return (
        "Hi! Send me:\n"
        "• A photo of your handwritten notes\n"
        "• Your session notes as text\n"
        "• A question about your campaign\n\n"
        "Type 'save: <notes>' to explicitly store a session dump."
    )


def _query_campaign(query: str, store: CampaignStore) -> str:
    """Simple semantic query against campaign memory via LLM."""
    import anthropic
    context = store.context_block(max_entities=30)
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                f"Campaign memory:\n{context}\n\n"
                f"GM question: {query}\n\n"
                "Answer concisely from the campaign memory above. "
                "If the answer isn't in the memory, say so."
            ),
        }],
    )
    return response.content[0].text.strip()


def _handle_image(media_url: str, media_type: str) -> Optional[str]:
    """Download image and extract text via OCR."""
    headers = {}
    provider = os.environ.get("WHATSAPP_PROVIDER", "twilio")
    if provider == "twilio":
        headers = {
            "Authorization": requests.auth.HTTPBasicAuth(
                os.environ["TWILIO_ACCOUNT_SID"],
                os.environ["TWILIO_AUTH_TOKEN"],
            )
        }
    elif provider == "meta":
        headers = {"Authorization": f"Bearer {os.environ['META_WHATSAPP_TOKEN']}"}

    resp = requests.get(media_url, headers=headers, timeout=30)
    if resp.status_code != 200:
        return None

    tmp_path = Path("/tmp") / f"loremind_scan_{hash(media_url)}.jpg"
    tmp_path.write_bytes(resp.content)
    text = extract_text_from_image(tmp_path)
    tmp_path.unlink(missing_ok=True)
    return text


def _get_meta_media_url(image_id: str) -> str:
    token = os.environ["META_WHATSAPP_TOKEN"]
    resp = requests.get(
        f"https://graph.facebook.com/v18.0/{image_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return resp.json().get("url", "")


def _current_session(store: CampaignStore) -> int:
    raw_dir = store.root / "raw"
    return len(list(raw_dir.glob("session-*.md"))) + 1
