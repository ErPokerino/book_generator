"""Readable title and author are composed after the optional generated background."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from app.services.usage_service import metered_call

async def make_cover(store, session):
    root = store.data_dir / "covers"
    root.mkdir(parents=True, exist_ok=True)
    background = Image.new("RGB", (1000, 1500), "#163b39")
    if session.form_data.cover_style != "typographic":
        import os
        from google import genai
        from google.genai import types
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Configura GOOGLE_API_KEY per creare una copertina illustrata.")
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=180000))
        model = "gemini-3.1-flash-image"
        try:
            result = await metered_call(lambda: client.aio.models.generate_content(model=model,
                contents="Crea lo sfondo di una copertina per un saggio adulto. Stile: " + session.form_data.cover_style +
                ". Tema: " + session.form_data.topic + ". Nessun testo, nessuna lettera. Lascia spazio nella metà superiore.",
                config=types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio="2:3"))),
                session_id=session.session_id, model=model, phase="essay-cover")
            image_data = next((p.inline_data.data for c in (result.candidates or []) for p in c.content.parts
                               if p.inline_data and p.inline_data.mime_type.startswith("image/")), None)
            if image_data is None:
                raise ValueError("Il servizio non ha restituito un'immagine.")
            background = Image.open(BytesIO(image_data)).convert("RGB").resize((1000,1500))
            veil = Image.new("RGB", background.size, "#163b39")
            background = Image.blend(background, veil, .55)
        finally:
            await client.aio.aclose()
            client.close()
    draw = ImageDraw.Draw(background)
    def font(size):
        path = Path("C:/Windows/Fonts/georgia.ttf")
        return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default(size=size)
    def wrap(text, face, width):
        tokens = []
        for word in text.split():
            chunk = ""
            for char in word:
                if chunk and draw.textlength(chunk + char, font=face) > width:
                    tokens.append(chunk)
                    chunk = char
                else:
                    chunk += char
            if chunk:
                tokens.append(chunk)
        lines, line = [], ""
        for word in tokens:
            candidate = line + " " + word if line else word
            if draw.textlength(candidate, font=face) > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines
    title = session.form_data.title or session.plan["title"]
    subtitle = session.form_data.subtitle or session.plan.get("subtitle", "")
    size, subtitle_size = 78, 31
    while size > 26:
        title_lines = wrap(title, font(size), 820)
        subtitle_lines = wrap(subtitle, font(subtitle_size), 820)
        if len(title_lines) * size * 1.25 + 60 + len(subtitle_lines) * subtitle_size * 1.45 <= 870:
            break
        size -= 2
        subtitle_size = max(18, subtitle_size - 1)
    draw.text((90, 110), "S A G G I A", font=font(27), fill="#d6bc8c")
    y = 300
    for line in wrap(title, font(size), 820):
        draw.text((90, y), line, font=font(size), fill="#fbf8f3")
        y += size * 1.25
    y += 60
    for line in wrap(subtitle, font(subtitle_size), 820):
        draw.text((90, y), line, font=font(subtitle_size), fill="#e7ddcb")
        y += subtitle_size * 1.45
    draw.line((90, 1230, 910, 1230), fill="#d6bc8c", width=2)
    author_size = 34
    while author_size > 18 and len(wrap(session.form_data.author_name, font(author_size), 820)) * author_size * 1.3 > 150:
        author_size -= 2
    for i, line in enumerate(wrap(session.form_data.author_name, font(author_size), 820)):
        draw.text((90, 1290+i*author_size*1.3), line, font=font(author_size), fill="#fbf8f3")
    target = root / (session.session_id + ".png")
    background.save(target)
    session = store.get_session(session.session_id)
    session.cover_image_path = str(target)
    store.save_session(session)
