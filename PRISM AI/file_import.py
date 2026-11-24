"""Normalize supported documents to PDF for the existing page evidence pipeline."""
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageSequence, ImageOps
try:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

TEXT = {'.txt', '.md', '.csv', '.tsv', '.json', '.jsonl', '.xml', '.html', '.htm',
        '.log', '.yaml', '.yml', '.py', '.js', '.ts', '.css', '.sql'}
IMAGES = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp', '.gif'}
SUPPORTED = TEXT | IMAGES | {'.pdf', '.docx', '.xlsx', '.pptx'}


def office_text(data, extension):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 128 * 1024 * 1024:
            raise ValueError('Expanded Office document exceeds 128 MiB.')
        def root(name):
            return ET.fromstring(archive.read(name))
        def local(tag):
            return tag.rsplit('}', 1)[-1]
        if extension == '.docx':
            return '\n'.join(''.join(e.text or '' for e in p.iter() if local(e.tag) == 't')
                             for p in root('word/document.xml').iter() if local(p.tag) == 'p')
        if extension == '.pptx':
            names = sorted((n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                           key=lambda n: int(re.search(r'slide(\d+)', n)[1]))
            return '\n\n'.join(f'Slide {i}\n' + '\n'.join(e.text or '' for e in root(n).iter() if local(e.tag) == 't')
                               for i, n in enumerate(names, 1))
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(e.text or '' for e in item.iter() if local(e.tag) == 't')
                      for item in root('xl/sharedStrings.xml')]
        output = []
        names = sorted(n for n in archive.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n))
        for name in names:
            output.append(name.rsplit('/', 1)[-1])
            for row in root(name).iter():
                if local(row.tag) != 'row':
                    continue
                cells = []
                for cell in row:
                    values = [e.text or '' for e in cell.iter() if local(e.tag) in ('v', 't')]
                    value = ' '.join(values)
                    if cell.get('t') == 's' and value:
                        value = shared[int(value)]
                    formula = next((e.text for e in cell if local(e.tag) == 'f'), None)
                    if formula and not value:
                        value = '[Formula without cached value: ' + formula + ']'
                    cells.append(cell.get('r', '') + ': ' + value)
                output.append(' | '.join(cells))
        return '\n'.join(output)


def to_pdf(name, data):
    extension = Path(name).suffix.lower()
    if extension not in SUPPORTED:
        raise ValueError('Unsupported format. Use PDF, DOCX, XLSX, PPTX, text/CSV/JSON, or PNG/JPEG/TIFF/WebP images. Export older DOC/XLS/PPT files to a supported format first.')
    if extension == '.pdf':
        return data
    if extension in IMAGES:
        with Image.open(io.BytesIO(data)) as source:
            frames = []
            for frame in ImageSequence.Iterator(source):
                if len(frames) >= 500:
                    raise ValueError('Image document exceeds 500 frames.')
                frames.append(ImageOps.exif_transpose(frame).convert('RGB'))
            output = io.BytesIO()
            frames[0].save(output, format='PDF', save_all=True, append_images=frames[1:])
            return output.getvalue()
    if extension in TEXT:
        try:
            text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('Save text files with UTF-8 or UTF-16 encoding and retry.') from exc
        if '\x00' in text:
            raise ValueError('This file contains binary data rather than readable text.')
    else:
        text = office_text(data, extension)
    if not text.strip():
        raise ValueError('No readable text found. Export this document to PDF if it contains only images or charts.')
    if len(text) > 2_000_000:
        raise ValueError('Text exceeds 2 million characters. Split the document into smaller files.')
    if not HAS_REPORTLAB:
        raise ValueError("Converting Office or plain text documents to PDF requires 'reportlab'. Please install reportlab or upload PDF documents directly.")
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    # Embed a Unicode TrueType font when available instead of losing accented text.
    for candidate in ('C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(candidate).is_file():
            if 'ImportUnicode' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('ImportUnicode', candidate))
            styles['Normal'].fontName = styles['Heading1'].fontName = 'ImportUnicode'
            break
    story = [Paragraph(escape(name), styles['Heading1']), Spacer(1, 12)]
    for line in text.splitlines():
        # Bound paragraphs so a single long line cannot stall layout.
        for start in range(0, max(1, len(line)), 2000):
            story.append(Paragraph(escape(line[start:start + 2000]) or '&#160;', styles['Normal']))
    SimpleDocTemplate(output).build(story)
    return output.getvalue()
