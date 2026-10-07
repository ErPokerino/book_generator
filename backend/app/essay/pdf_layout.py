"""Book typography and semantic Markdown for the SaggIA PDF edition."""
from __future__ import annotations

from functools import lru_cache
from html import escape, unescape
from io import BytesIO
from pathlib import Path
import re
import json
from types import SimpleNamespace
from threading import Lock
import xml.etree.ElementTree as ET

import markdown
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Flowable, Frame, HRFlowable, ListFlowable,
    ListItem, LongTable, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

INK = colors.HexColor("#163b39")
GOLD = colors.HexColor("#a2804b")
TEXT = colors.HexColor("#292c29")
MUTED = colors.HexColor("#70746b")
PAPER = colors.HexColor("#f4f0ea")
RULE = colors.HexColor("#d9d4ca")
FONT_LOCK = Lock()


@lru_cache(maxsize=1)
def fonts():
    """Embed installed fonts, with portable serif/sans fallbacks."""
    families = [
        (Path("C:/Windows/Fonts"), ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2"),
         ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu"),
         ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf", "DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf")),
    ]
    serif = "Times-Roman"
    italic = "Times-Italic"
    sans = "Helvetica"
    with FONT_LOCK:
        for directory, names in families:
            if all((directory / name).is_file() for name in names):
                for suffix, name in zip(("", "-Bold", "-Italic", "-BoldItalic"), names):
                    pdfmetrics.registerFont(TTFont("SaggiaSerif" + suffix, str(directory / name)))
                pdfmetrics.registerFontFamily("SaggiaSerif", normal="SaggiaSerif",
                    bold="SaggiaSerif-Bold", italic="SaggiaSerif-Italic", boldItalic="SaggiaSerif-BoldItalic")
                serif, italic = "SaggiaSerif", "SaggiaSerif-Italic"
                break
        arial = Path("C:/Windows/Fonts/arial.ttf")
        if arial.is_file():
            pdfmetrics.registerFont(TTFont("SaggiaSans", str(arial)))
            bold = arial.with_name("arialbd.ttf")
            if bold.is_file():
                pdfmetrics.registerFont(TTFont("SaggiaSans-Bold", str(bold)))
            pdfmetrics.registerFontFamily("SaggiaSans", normal="SaggiaSans",
                bold="SaggiaSans-Bold" if bold.is_file() else "SaggiaSans", italic="SaggiaSans")
            sans = "SaggiaSans"
    return serif, italic, sans


def styles():
    serif, italic, sans = fonts()
    body = ParagraphStyle("BookBody", fontName=serif, fontSize=10.3, leading=15.4,
        alignment=TA_JUSTIFY, textColor=TEXT, firstLineIndent=12, spaceAfter=5,
        allowWidows=0, allowOrphans=0, splitLongWords=True)
    return {
        "body": body,
        "first": ParagraphStyle("BookFirst", parent=body, firstLineIndent=0),
        "chapter": ParagraphStyle("BookChapter", fontName=serif, fontSize=23, leading=29,
            textColor=INK, spaceAfter=21, keepWithNext=True, splitLongWords=True),
        "kicker": ParagraphStyle("BookKicker", fontName=sans, fontSize=8, leading=12,
            textColor=GOLD, spaceAfter=10, keepWithNext=True),
        "heading": ParagraphStyle("BookHeading", fontName=serif, fontSize=14, leading=19,
            textColor=INK, spaceBefore=17, spaceAfter=9, keepWithNext=False),
        "subheading": ParagraphStyle("BookSubheading", fontName=serif, fontSize=11.5, leading=16,
            textColor=INK, spaceBefore=12, spaceAfter=7, keepWithNext=False),
        "quote": ParagraphStyle("BookQuote", parent=body, fontName=italic, fontSize=10,
            firstLineIndent=0, leftIndent=12, rightIndent=10, spaceBefore=10, spaceAfter=12,
            textColor=colors.HexColor("#4d584a")),
        "list": ParagraphStyle("BookList", parent=body, firstLineIndent=0, spaceAfter=5),
        "table": ParagraphStyle("BookTable", fontName=serif, fontSize=8.2, leading=11.6,
            textColor=TEXT, splitLongWords=True),
        "table_head": ParagraphStyle("BookTableHead", fontName=sans, fontSize=7.5,
            leading=10.5, textColor=INK, splitLongWords=True),
        "code": ParagraphStyle("BookCode", fontName=sans, fontSize=8, leading=12,
            textColor=TEXT, backColor=PAPER, borderPadding=8, spaceBefore=8, spaceAfter=12),
        "reference": ParagraphStyle("BookReference", parent=body, fontSize=9, leading=13.5,
            alignment=0, firstLineIndent=-13, leftIndent=13, spaceAfter=11),
        "contents": ParagraphStyle("BookContents", fontName=serif, fontSize=10.1, leading=15,
            textColor=TEXT, leftIndent=0, firstLineIndent=0, rightIndent=20, spaceBefore=9),
    }


def inline(element, style_set):
    """Translate a small safe HTML subset without fetching remote resources."""
    result = escape(element.text or "")
    for child in element:
        text = inline(child, style_set)
        if child.tag in ("strong", "b"):
            text = "<b>" + text + "</b>"
        elif child.tag in ("em", "i"):
            text = "<i>" + text + "</i>"
        elif child.tag == "code":
            text = '<font name="' + fonts()[2] + '">' + text + "</font>"
        elif child.tag == "a":
            url = child.get("href", "")
            if re.match(r"^https?://", url, re.I):
                text = '<a href="' + escape(url, quote=True) + '" color="#355b55">' + text + "</a>"
        elif child.tag == "br":
            text = "<br/>"
        elif child.tag == "img":
            text = escape(child.get("alt", ""))
        result += text + escape(child.tail or "")
    return result


def markdown_flowables(content, style_set, width):
    # Raw HTML and external images remain data; PDF export never executes/fetches them.
    content = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", content)
    html = markdown.markdown(content.replace("<", "&lt;"), extensions=["tables"], output_format="xhtml")
    html = re.sub(r"&[a-zA-Z][a-zA-Z0-9]+;", lambda m: escape(unescape(m.group())), html)
    root = ET.fromstring("<root>" + html + "</root>")
    flow = []
    first = True

    def convert(node):
        nonlocal first
        tag = node.tag
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            first = True
            heading = Paragraph(inline(node, style_set), style_set["heading" if tag in ("h1", "h2") else "subheading"])
            _, height = heading.wrap(width, 1000)
            return [CondPageBreak(height + heading.style.spaceBefore + heading.style.spaceAfter + 2 * style_set["body"].leading), heading]
        if tag == "p":
            para = Paragraph(inline(node, style_set), style_set["first" if first else "body"])
            first = False
            return [para]
        if tag in ("ul", "ol"):
            first = True
            items = []
            for child in node:
                if child.tag != "li":
                    continue
                parts = []
                if child.text and child.text.strip():
                    # Clone the inline portion separately from nested block lists.
                    fragment = ET.Element("p")
                    fragment.text = child.text
                    for inner in child:
                        if inner.tag not in ("ul", "ol", "p"):
                            fragment.append(inner)
                    parts.append(Paragraph(inline(fragment, style_set), style_set["list"]))
                for inner in child:
                    if inner.tag in ("ul", "ol", "p"):
                        parts.extend(convert(inner))
                if not parts:
                    parts = [Paragraph(inline(child, style_set), style_set["list"])]
                items.append(ListItem(parts))
            if not items:
                return []
            return [ListFlowable(items, bulletType="1" if tag == "ol" else "bullet",
                start=int(node.get("start", "1")) if tag == "ol" else None,
                leftIndent=14, bulletFontName=fonts()[2], bulletFontSize=7,
                spaceBefore=6, spaceAfter=8)]
        if tag == "blockquote":
            first = True
            return [Paragraph(inline(child, style_set), style_set["quote"]) for child in node]
        if tag == "table":
            first = True
            rows = node.findall(".//tr")
            cells = [[cell for cell in row if cell.tag in ("td", "th")] for row in rows]
            columns = max((len(row) for row in cells), default=0)
            if not columns:
                return []
            header = bool(cells[0] and cells[0][0].tag == "th")
            data = [[Paragraph(inline(cell, style_set), style_set["table_head" if i == 0 and header else "table"])
                     for cell in row] + [""] * (columns - len(row)) for i, row in enumerate(cells)]
            table = LongTable(data, colWidths=[width / columns] * columns, repeatRows=1 if header else 0,
                splitByRow=1, splitInRow=1, hAlign="LEFT", spaceBefore=8, spaceAfter=13)
            table.setStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, -1), .35, RULE),
            ] + ([("BACKGROUND", (0, 0), (-1, 0), PAPER), ("LINEBELOW", (0, 0), (-1, 0), .8, GOLD)] if header else []))
            return [table]
        if tag == "pre":
            first = True
            return [Paragraph(escape("".join(node.itertext())).replace("\n", "<br/>"), style_set["code"])]
        if tag == "hr":
            first = True
            return [HRFlowable(width="100%", thickness=.4, color=RULE, spaceBefore=12, spaceAfter=12)]
        return [Paragraph(inline(node, style_set), style_set["first"])] if "".join(node.itertext()).strip() else []

    for node in root:
        flow.extend(convert(node))
    return flow


def clipped(text, font, size, width):
    text = " ".join(text.split())
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "...", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "..."


class TitleLeaf(Flowable):
    def __init__(self, title, subtitle, author, note):
        super().__init__()
        self.title, self.subtitle, self.author, self.note = title, subtitle, author, note

    def wrap(self, width, height):
        self.width, self.height = width, height - 1
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        serif, italic, sans = fonts()
        y = self.height - 38
        canvas.setFillColor(GOLD)
        canvas.setFont(sans, 8)
        canvas.drawString(0, y, "SAGGISTICA")
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(.8)
        canvas.line(0, y - 15, 32, y - 15)
        y -= 42
        size = 25
        while True:
            style = ParagraphStyle("TitleLeaf", fontName=serif, fontSize=size, leading=size * 1.2, textColor=INK)
            title = Paragraph(escape(self.title), style)
            _, height = title.wrap(self.width, self.height)
            if height <= (self.height - 190) * .50 or size <= 10:
                break
            size -= 1
        title.drawOn(canvas, 0, y - height)
        y -= height + 21
        for text, font, size, color, max_height in [
            (self.subtitle, italic, 11.5, MUTED, (self.height - 190) * .32),
            (self.author, serif, 12, INK, (self.height - 190) * .18),
        ]:
            if not text:
                continue
            while True:
                para = Paragraph(escape(text), ParagraphStyle("TitleMeta", fontName=font,
                    fontSize=size, leading=size * 1.45, textColor=color))
                _, height = para.wrap(self.width, self.height)
                if height <= max_height or size <= 7:
                    break
                size -= .5
            para.drawOn(canvas, 0, y - height)
            y -= height + 19
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(.5)
        canvas.line(0, 38, self.width, 38)
        if self.note:
            note = Paragraph(escape(self.note), ParagraphStyle("TitleNote", fontName=sans,
                fontSize=7, leading=10, textColor=MUTED))
            _, height = note.wrap(self.width, 35)
            note.drawOn(canvas, 0, 31 - height)
        else:
            canvas.setFont(sans, 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawString(0, 22, "Edizione digitale")


class CoverLeaf(Flowable):
    def __init__(self, path):
        super().__init__()
        self.image = ImageReader(path)

    def wrap(self, width, height):
        self.width, self.height = width, height - 1
        return self.width, self.height

    def draw(self):
        self.canv.setFillColor(PAPER)
        self.canv.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        iw, ih = self.image.getSize()
        scale = min(self.width / iw, self.height / ih)
        width, height = iw * scale, ih * scale
        self.canv.drawImage(self.image, (self.width - width) / 2, (self.height - height) / 2,
            width=width, height=height, mask="auto")


class BackCoverLeaf(Flowable):
    def __init__(self, title, text, author):
        super().__init__()
        self.title, self.text, self.author = title, text, author

    def wrap(self, width, height):
        self.width, self.height = width, height - 1
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        serif, italic, sans = fonts()
        canvas.setFillColor(INK)
        canvas.rect(0, 0, self.width, self.height + 1, stroke=0, fill=1)
        left, width = 24 * mm, self.width - 48 * mm
        top = self.height - 31 * mm
        canvas.setFillColor(GOLD)
        canvas.setFont(sans, 8)
        canvas.drawString(left, top, "S A G G I A")
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(.8)
        canvas.line(left, top - 12, left + 35, top - 12)
        y = top - 48
        blocks = [block.strip() for block in re.split(r"\n\s*\n", self.text) if block.strip()]
        # Preserve up to three paragraphs; excess manual line breaks must not overflow a single back page.
        if len(blocks) > 3:
            blocks = [*blocks[:2], " ".join(blocks[2:])]
        size = 11.5
        while True:
            heading = Paragraph(escape(self.title), ParagraphStyle("BackTitle", fontName=serif,
                fontSize=min(19, size * 1.65), leading=min(24, size * 2.1), textColor=PAPER))
            paragraphs = [Paragraph(" ".join(escape(block).split()), ParagraphStyle("BackText",
                fontName=serif, fontSize=size, leading=size * 1.5, textColor=PAPER)) for block in blocks]
            author = Paragraph(escape(self.author), ParagraphStyle("BackAuthor", fontName=italic,
                fontSize=size, leading=size * 1.4, textColor=GOLD)) if self.author else None
            items = [heading, *paragraphs, *([author] if author else [])]
            heights = [item.wrap(width, self.height)[1] for item in items]
            if sum(heights) + 18 * len(items) <= y - 38 * mm:
                break
            if size <= 6.5:
                raise ValueError("La quarta di copertina è troppo lunga per una pagina leggibile. Riduci il testo o il titolo.")
            size -= .25
        for item, height in zip(items, heights):
            item.drawOn(canvas, left, y - height)
            y -= height + 18
        canvas.setStrokeColor(GOLD)
        canvas.line(left, 26 * mm, self.width - left, 26 * mm)
        canvas.setFont(sans, 7)
        canvas.setFillColor(GOLD)
        canvas.drawString(left, 18 * mm, "SAGGISTICA")


class BookDocument(BaseDocTemplate):
    def __init__(self, output, title, author):
        super().__init__(output, pagesize=A5, leftMargin=21 * mm, rightMargin=19 * mm,
            topMargin=21 * mm, bottomMargin=22 * mm, title=title, author=author,
            pageCompression=1, allowSplitting=1)
        self.book_title = title
        self.addPageTemplates([
            PageTemplate("cover", [Frame(0, 0, A5[0], A5[1], leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]),
            PageTemplate("front", [self.text_frame("front")]),
            PageTemplate("body", [self.text_frame("body")], onPageEnd=self.furniture),
            PageTemplate("back", [Frame(0, 0, A5[0], A5[1], leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]),
        ])

    def text_frame(self, name):
        return Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
            id=name, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def beforeDocument(self):
        self.body_start = None
        self.current_chapter = ""
        self.opener_page = None

    def afterFlowable(self, flowable):
        section = getattr(flowable, "book_section", None)
        if section:
            title, key = section
            if self.body_start is None:
                self.body_start = self.page
            self.current_chapter, self.opener_page = title, self.page
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=0, closed=False)
            self.notify("TOCEntry", (0, escape(title), self.page - self.body_start + 1, key))

    def furniture(self, canvas, doc):
        if self.body_start is None:
            return
        number = self.page - self.body_start + 1
        serif, italic, sans = fonts()
        canvas.saveState()
        canvas.setFillColor(MUTED)
        if self.page != self.opener_page:
            header = self.current_chapter if number % 2 else self.book_title
            canvas.setFont(italic, 7)
            canvas.drawString(self.leftMargin, A5[1] - 12 * mm,
                clipped(header, italic, 7, self.width))
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(.4)
            canvas.line(self.leftMargin, A5[1] - 14 * mm, A5[0] - self.rightMargin, A5[1] - 14 * mm)
        canvas.setFont(sans, 8)
        if number % 2:
            canvas.drawRightString(A5[0] - self.rightMargin, 12 * mm, str(number))
        else:
            canvas.drawString(self.leftMargin, 12 * mm, str(number))
        canvas.restoreState()


def section_heading(title, key, kicker, style_set):
    heading = Paragraph(escape(title), style_set["chapter"])
    heading.book_section = (title, key)
    return [
        Spacer(1, 25),
        HRFlowable(width=30, thickness=1, color=GOLD, hAlign="LEFT", spaceAfter=15),
        Paragraph(kicker, style_set["kicker"]), heading,
    ]


def _render_pdf(session, chapters, bibliography, title, subtitle, author, work_note, back_text):
    style_set = styles()
    output = BytesIO()
    doc = BookDocument(output, title, author)
    story = []
    cover = session.cover_image_path
    if cover and Path(cover).is_file():
        story += [CoverLeaf(cover), NextPageTemplate("front"), PageBreak()]
    else:
        story.append(NextPageTemplate("front"))
        # Select the front template for the first page when there is no cover.
        doc.pageTemplates = [doc.pageTemplates[1], doc.pageTemplates[0], *doc.pageTemplates[2:]]
    story += [TitleLeaf(title, subtitle, author, work_note), PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [style_set["contents"]]
    toc.dotsMinLevel = 0
    story += [Spacer(1, 25), Paragraph("CONTENUTI", style_set["kicker"]),
        Paragraph("Indice", style_set["chapter"]), Spacer(1, 12), toc]
    for index, chapter in enumerate(chapters, 1):
        story += [NextPageTemplate("body"), PageBreak()]
        story += section_heading(chapter["title"], "chapter-" + str(index), "CAPITOLO " + str(index).zfill(2), style_set)
        story += markdown_flowables(chapter["display_content"], style_set, doc.width)
    if bibliography:
        story += [NextPageTemplate("body"), PageBreak()]
        story += section_heading("Bibliografia", "bibliography", "FONTI E RIFERIMENTI", style_set)
        for source in bibliography:
            story.append(Paragraph(escape("[" + source["label"] + "] " + source["text"]), style_set["reference"]))
    story += [NextPageTemplate("back"), PageBreak(), BackCoverLeaf(title, back_text, author)]
    doc.multiBuild(story, maxPasses=8)
    return output.getvalue(), "application/pdf"


@lru_cache(maxsize=8)
def _cached_pdf(payload, cover_signature):
    # The key includes text, references, edition metadata and the current cover.
    # A bounded memory cache lets Opere report the same page count as downloads.
    values = json.loads(payload)
    return _render_pdf(SimpleNamespace(cover_image_path=values.pop("cover")), **values)


def export_pdf(session, chapters, bibliography, title, subtitle, author, work_note, back_text):
    cover = session.cover_image_path
    signature = None
    if cover and Path(cover).is_file():
        stat = Path(cover).stat()
        signature = (stat.st_mtime_ns, stat.st_size)
    payload = json.dumps({"cover": cover, "chapters": chapters, "bibliography": bibliography,
        "title": title, "subtitle": subtitle, "author": author, "work_note": work_note, "back_text": back_text},
        ensure_ascii=False, sort_keys=True)
    return _cached_pdf(payload, signature)
