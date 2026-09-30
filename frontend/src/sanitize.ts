import DOMPurify from 'dompurify';

export function safeArtifact(html: string): string {
  const clean = DOMPurify.sanitize(html, {
    WHOLE_DOCUMENT: true,
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'textarea', 'select', 'meta', 'base', 'link', 'a', 'svg', 'math'],
    FORBID_ATTR: ['src', 'srcset', 'href', 'action', 'formaction', 'target', 'xlink:href'],
  });
  const policy = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; script-src 'none'; connect-src 'none'; form-action 'none'; base-uri 'none'";
  const head = `<meta http-equiv="Content-Security-Policy" content="${policy}"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{font-family:system-ui,sans-serif;line-height:1.65;padding:24px;color:#203c33;overflow-wrap:anywhere}*{box-sizing:border-box;max-width:100%}</style>`;
  return clean.includes('<head>') ? clean.replace('<head>', `<head>${head}`) : `<!doctype html><html><head>${head}</head><body>${clean}</body></html>`;
}
