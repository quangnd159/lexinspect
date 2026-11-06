// Reading a file into the editor, entirely in the browser.
//
// Plain text and Markdown are read as they are. Word (.docx) and OpenDocument
// (.odt) files are ZIP archives holding the body as XML: the archive's central
// directory is parsed here, the one XML entry inflated with the browser's own
// DecompressionStream, and the paragraphs taken out with DOMParser. Paragraphs
// are joined by blank lines, which the analyser treats as sentence ends, so a
// heading without a full stop never runs into the paragraph after it.

const Files = (() => {
  const MAX_FILE_BYTES = 20 * 1024 * 1024;
  const ACCEPT = '.txt,.md,.markdown,.text,.docx,.odt,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.oasis.opendocument.text';

  class FileError extends Error {}

  function ext(name) {
    const m = /\.([a-z0-9]+)$/i.exec(name || '');
    return m ? m[1].toLowerCase() : '';
  }

  // ---- ZIP ---------------------------------------------------------------------

  /** The bytes of one archive entry, inflated. */
  async function zipEntry(buf, wanted) {
    const view = new DataView(buf);
    // End of central directory: signature 0x06054b50, within the last 64 KB + 22 bytes.
    let eocd = -1;
    for (let i = buf.byteLength - 22; i >= Math.max(0, buf.byteLength - 65557); i--) {
      if (view.getUint32(i, true) === 0x06054b50) {
        eocd = i;
        break;
      }
    }
    if (eocd < 0) throw new FileError(t('This file can’t be read as a document. It may be damaged or saved in an older format. Save it as .docx or plain text and try again.'));
    const entries = view.getUint16(eocd + 10, true);
    let p = view.getUint32(eocd + 16, true);
    const dec = new TextDecoder();
    for (let n = 0; n < entries; n++) {
      if (view.getUint32(p, true) !== 0x02014b50) break;
      const method = view.getUint16(p + 10, true);
      const size = view.getUint32(p + 20, true);
      const nameLen = view.getUint16(p + 28, true);
      const extraLen = view.getUint16(p + 30, true);
      const commentLen = view.getUint16(p + 32, true);
      const local = view.getUint32(p + 42, true);
      const name = dec.decode(new Uint8Array(buf, p + 46, nameLen));
      p += 46 + nameLen + extraLen + commentLen;
      if (name !== wanted) continue;
      const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
      const raw = new Uint8Array(buf, start, size);
      if (method === 0) return raw;
      if (method !== 8) throw new FileError(t('This document uses an unsupported compression method. Save it again from your word processor, or paste the text in.'));
      const stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
      return new Uint8Array(await new Response(stream).arrayBuffer());
    }
    return null;
  }

  // ---- document XML ----------------------------------------------------------------

  // Never walked: paragraph and run properties (w:pPr holds tab-stop
  // definitions, also named w:tab), and the fallback copy Word keeps of every
  // text box (mc:Fallback repeats what mc:Choice holds).
  const SKIP = new Set(['pPr', 'rPr', 'Fallback', 'delText', 'instrText', 'note', 'footnoteReference']);

  function paragraphs(xml, { para, run }) {
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    if (doc.getElementsByTagName('parsererror').length) throw new FileError(t('The document’s text couldn’t be read. Paste it in instead.'));
    const out = [];
    // A paragraph's own text, then the paragraphs nested in it (text boxes,
    // tables in cells), each as a paragraph of its own and each once.
    const visit = (p) => {
      let s = '';
      const nested = [];
      const walk = (node) => {
        for (const c of node.childNodes) {
          if (c.nodeType === 3) {
            if (run(node)) s += c.nodeValue;
          } else if (c.nodeType === 1) {
            if (para(c)) {
              nested.push(c);
              continue;
            }
            const tag = c.localName;
            if (SKIP.has(tag)) continue;
            if (tag === 'tab') s += '\t';
            else if (tag === 'br' || tag === 'line-break' || tag === 'cr') s += '\n';
            else if (tag === 's') s += ' '.repeat(Number(c.getAttributeNS(c.namespaceURI, 'c') || c.getAttribute('text:c') || 1));
            else walk(c);
          }
        }
      };
      walk(p);
      s = s.replace(/[ \t]+$/g, '');
      if (s.trim()) out.push(s);
      nested.forEach(visit);
    };
    for (const p of doc.getElementsByTagNameNS('*', '*')) {
      if (para(p) && !(p.parentElement && hasAncestor(p.parentElement, para))) visit(p);
    }
    return out.join('\n\n');
  }

  /** Whether `el` or an element above it passes `test`. */
  function hasAncestor(el, test) {
    for (let e = el; e; e = e.parentElement) if (test(e)) return true;
    return false;
  }

  async function docx(buf) {
    const xml = await zipEntry(buf, 'word/document.xml');
    if (!xml) throw new FileError(t('No document text was found in this file. Check that it is a Word (.docx) document.'));
    return paragraphs(new TextDecoder().decode(xml), {
      para: (e) => e.localName === 'p' && /wordprocessingml/.test(e.namespaceURI || ''),
      run: (e) => e.localName === 't',
    });
  }

  async function odt(buf) {
    const xml = await zipEntry(buf, 'content.xml');
    if (!xml) throw new FileError(t('No document text was found in this file. Check that it is an OpenDocument text (.odt) file.'));
    return paragraphs(new TextDecoder().decode(xml), {
      para: (e) => (e.localName === 'p' || e.localName === 'h') && /opendocument/.test(e.namespaceURI || ''),
      run: () => true,
    });
  }

  function plain(buf) {
    const bytes = new Uint8Array(buf);
    // UTF-16 with a byte-order mark (Notepad's "Unicode"); otherwise UTF-8, and
    // Windows-1252 if that fails to decode.
    if (bytes[0] === 0xff && bytes[1] === 0xfe) return new TextDecoder('utf-16le').decode(bytes);
    if (bytes[0] === 0xfe && bytes[1] === 0xff) return new TextDecoder('utf-16be').decode(bytes);
    try {
      return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    } catch {
      return new TextDecoder('windows-1252').decode(bytes);
    }
  }

  /** The text of a File, or a FileError saying why not. */
  async function read(file) {
    if (file.size > MAX_FILE_BYTES) throw new FileError(t('{name} is {size} MB. Files up to 20 MB can be opened.', { name: quoted(file.name), size: num(file.size / 1e6, 1) }));
    const kind = ext(file.name);
    const buf = await file.arrayBuffer();
    let text;
    if (kind === 'docx') text = await docx(buf);
    else if (kind === 'odt') text = await odt(buf);
    else if (kind === 'pdf') throw new FileError(t('PDF files can’t be opened. Open the PDF, copy its text and paste it in.'));
    else if (kind === 'doc' || kind === 'rtf' || kind === 'pages') throw new FileError(t('.{ext} files can’t be opened. Save the document as .docx or plain text, or paste the text in.', { ext: kind }));
    else if (!kind || ['txt', 'md', 'markdown', 'text'].includes(kind) || file.type.startsWith('text/')) text = plain(buf);
    else throw new FileError(t('.{ext} files can’t be opened. Use a .txt, .md, .docx or .odt file, or paste the text in.', { ext: kind }));
    text = text.replace(/\r\n?/g, '\n').replace(/^﻿/, '');
    if (!text.trim()) throw new FileError(t('{name} has no text in it.', { name: quoted(file.name) }));
    return text;
  }

  return { read, ACCEPT, FileError };
})();
