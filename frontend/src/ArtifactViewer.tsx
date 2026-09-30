import { useState } from 'react';
import { Download, FileText, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { safeArtifact } from './sanitize';
import type { Artifact } from './types';

export function Markdown({ children }: { children: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]} skipHtml>{children}</ReactMarkdown>;
}

export function ArtifactViewer({ artifact, close }: { artifact: Artifact; close: () => void }) {
  const [tab, setTab] = useState<'preview' | 'source'>('preview');
  const words = artifact.content.trim().split(/\s+/).length;
  function download() {
    const html = artifact.artifact_type === 'html';
    const blob = new Blob([html ? safeArtifact(artifact.content) : artifact.content], { type: html ? 'text/html' : 'text/markdown' });
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = `lenny-growth-brief.${html ? 'html' : 'md'}`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <aside className="artifact-panel" aria-label="Artifact viewer">
    <header><div className="flex items-center gap-2"><FileText size={17}/><strong>Writing studio</strong></div><button className="icon-button" aria-label="Close artifact" onClick={close}><X size={18}/></button></header>
    <div className="artifact-toolbar"><div className="segmented"><button className={tab === 'preview' ? 'selected' : ''} onClick={() => setTab('preview')}>Preview</button><button className={tab === 'source' ? 'selected' : ''} onClick={() => setTab('source')}>Source</button></div><button className="icon-button" aria-label="Download artifact" onClick={download}><Download size={17}/></button></div>
    <div className="artifact-caption"><span>{artifact.title}</span><span>{artifact.artifact_type === 'markdown' ? `${words.toLocaleString()} words` : 'Sandboxed HTML'}</span></div>
    {tab === 'source' ? <pre className="source-code">{artifact.content}</pre> : artifact.artifact_type === 'html' ? <iframe title={artifact.title} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={safeArtifact(artifact.content)}/> : <article className="document prose"><Markdown>{artifact.content}</Markdown></article>}
    <footer>Built from the archive. Review the evidence before sharing.</footer>
  </aside>;
}
