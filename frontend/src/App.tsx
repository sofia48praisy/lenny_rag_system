import { useEffect, useRef, useState } from 'react';
import { ArrowUp, ArrowUpRight, BookOpen, Check, ChevronRight, CircleHelp, FileText, Headphones, LoaderCircle, MessageSquare, Plus, RefreshCw, Sparkles, Terminal } from 'lucide-react';
import { api, readEvents } from './api';
import { ArtifactViewer, Markdown } from './ArtifactViewer';
import type { Artifact, Health, Message, Session, Source } from './types';

const suggestions = [
  { tag: 'PRODUCT STRATEGY', title: 'How is AI changing product teams?', query: 'What does Adam Mosseri say about how AI is changing the structure of product teams?' },
  { tag: 'GROWTH', title: 'Build a growth engine that lasts', query: 'What does Elena Verna recommend about growing AI products?' },
  { tag: 'LEADERSHIP', title: 'Learn from experienced founders', query: 'What advice does Brian Halligan give founders about leadership?' },
];

function SourceCard({ source }: { source: Source }) {
  const url = /^https?:\/\//i.test(source.url) ? source.url : undefined;
  return <details className="source-card"><summary><BookOpen size={14}/><span>{source.guest}<small>{source.timestamp} · {(source.score * 100).toFixed(0)}% similarity</small></span><ChevronRight size={14}/></summary><div className="source-detail"><strong>{source.episode}</strong><p>{source.excerpt}</p>{url && <a href={url} target="_blank" rel="noreferrer">Open original source ↗</a>}</div></details>;
}

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]), [sessionId, setSessionId] = useState('');
  const [messages, setMessages] = useState<Message[]>([]), [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('ollama'), [mode, setMode] = useState('answer');
  const [health, setHealth] = useState<Health | null>(null), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [phase, setPhase] = useState(''), [stream, setStream] = useState('');
  const [sources, setSources] = useState<Source[]>([]), [artifact, setArtifact] = useState<Artifact | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const end = useRef<HTMLDivElement>(null), guard = useRef(false);

  async function refresh() {
    const [sessionResult, healthResult] = await Promise.allSettled([
      api<Session[]>('/sessions'), fetch('/api/health').then(async r => { const data = await r.json(); if (!data.status) throw new Error('Invalid health response'); return data as Health; }),
    ]);
    if (sessionResult.status === 'fulfilled') setSessions(sessionResult.value);
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value); else setHealth(null);
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'auto', block: 'end' }); }, [stream, messages]);

  async function openSession(id: string) {
    if (guard.current) return;
    if (!id) { setSessionId(''); setMessages([]); setArtifact(null); setError(''); return; }
    guard.current = true; setBusy(true);
    try {
      const data = await api<Session & { messages: Message[] }>(`/sessions/${id}`);
      setSessionId(id); setMessages(data.messages); setArtifact(null); setError('');
    } catch (err) { setError((err as Error).message); }
    finally { guard.current = false; setBusy(false); }
  }

  async function send(value = question) {
    if (!value.trim() || guard.current) return;
    guard.current = true; setBusy(true); setError(''); setStream(''); setSources([]); setLatency(null);
    setPhase('Finding evidence in the archive…'); setQuestion('');
    const previous = messages;
    let committed = false;
    try {
      let id = sessionId;
      if (!id) {
        const session = await api<Session>('/sessions', { method: 'POST', body: JSON.stringify({ title: 'New research' }) });
        id = session.id; setSessionId(id); setSessions(s => [session, ...s]);
      }
      setMessages([...previous, { id: 'pending-user', role: 'user', content: value, sources: [] }]);
      const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: id, question: value, provider, mode }) });
      await readEvents(response, (event, data) => {
        if (event === 'sources') { setSources(data as Source[]); setPhase('Writing from retrieved evidence…'); }
        if (event === 'token') setStream(s => s + (data as { text: string }).text);
        if (event === 'message') {
          const message = data as Message;
          committed = true;
          setMessages([...previous, { id: `user-${message.id}`, role: 'user', content: value, sources: [] }, message]);
          setStream(''); setSources([]);
          if (message.artifact) setArtifact(message.artifact);
        }
        if (event === 'done') setLatency((data as { first_token_ms: number | null }).first_token_ms);
      });
      void refresh();
    } catch (err) {
      setError((err as Error).message);
      if (!committed) { setMessages(previous); setQuestion(value); }
    } finally { setBusy(false); guard.current = false; setPhase(''); setStream(''); setSources([]); }
  }

  return <div className={`workspace ${artifact ? 'has-artifact' : ''}`}>
    <nav className="sidebar" aria-label="Research sessions">
      <a className="brand" href="/" aria-label="Lenny home"><span className="brand-icon"><Headphones size={22}/></span><span>lenny<span className="brand-dot">.</span><small>GROWTH ASSISTANT</small></span></a>
      <button className="new-session" disabled={busy} onClick={() => void openSession('')}><Plus size={17}/> New research <span>↗</span></button>
      <div className="nav-section"><span className="eyebrow">YOUR WORKSPACE</span><div className="nav-active"><MessageSquare size={17}/> Conversations</div><div className="archive-link"><BookOpen size={17}/> Podcast archive <span>{health?.episodes ?? '—'}</span></div></div>
      <div className="session-section"><span className="eyebrow">RECENT RESEARCH</span>{sessions.length ? sessions.map(s => <button title={s.title} className={s.id === sessionId ? 'active-session' : ''} disabled={busy} key={s.id} onClick={() => void openSession(s.id)}><MessageSquare size={14}/><span>{s.title}</span></button>) : <p className="empty-history">Your conversations will live here.</p>}</div>
      <div className="sidebar-bottom"><div className="local-note"><span className="status-dot"/> Local-first intelligence<p>Your archive. Your model.<br/>Answers with evidence.</p></div><div className="profile"><span>LG</span><div>Growth workspace<small>Single-user edition</small></div><CircleHelp size={16}/></div></div>
    </nav>
    <main className="main-pane">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={13}/><strong>Growth assistant</strong></div><span className="provider-badge"><span className="status-dot"/>{provider === 'ollama' ? 'Ollama · Local' : 'Anthropic · Cloud'}</span></header>
      <div className="mobile-sessions"><select aria-label="Research session" disabled={busy} value={sessionId} onChange={e => void openSession(e.target.value)}><option value="">New research</option>{sessions.map(s => <option value={s.id} key={s.id}>{s.title}</option>)}</select></div>
      {health?.status !== 'ready' && <div className="health-banner"><Terminal size={16}/><span>{health ? `Setup pending: ${[!health.database && 'database', !health.embedding_model && 'embedding model', !health.chat_model && 'chat model', !health.chunks && 'transcript ingestion'].filter(Boolean).join(', ') || 'vector index'}. See README for setup.` : 'Backend not connected. Start the Docker Compose stack to begin.'}</span><button className="icon-button" aria-label="Refresh service health" onClick={() => void refresh()}><RefreshCw size={14}/></button></div>}
      <section className="conversation" aria-label="Conversation">
        {!messages.length && !busy ? <div className="welcome"><div className="welcome-symbol"><Sparkles size={26}/></div><div className="welcome-kicker">THE LENNY KNOWLEDGE WORKSPACE</div><h1>Good questions.<br/><em>Great growth.</em></h1><p>Turn the best minds in product and growth into your<br className="desktop-break"/> next move. Grounded in conversations. Backed by sources.</p><div className="suggestions">{suggestions.map(s => <button key={s.tag} onClick={() => setQuestion(s.query)}><span>{s.tag}</span><strong>{s.title}</strong><ArrowUpRight size={18}/></button>)}</div><div className="archive-note"><BookOpen size={14}/>{health?.chunks ? `${health.episodes} episodes · ${health.chunks.toLocaleString()} searchable passages` : 'Real podcast transcripts. Traceable insights.'}</div></div> : <div className="messages">{messages.map(m => <article className={`message ${m.role}`} key={m.id}><div className="message-avatar">{m.role === 'user' ? 'YOU' : <Headphones size={17}/>}</div><div className="message-body"><div className="message-label">{m.role === 'user' ? 'You' : 'Lenny Growth Assistant'}</div>{m.artifact ? <button className="artifact-card" onClick={() => setArtifact(m.artifact!)}><FileText size={25}/><span><strong>{m.artifact.title}</strong><small>Open in the writing studio</small></span><ArrowUpRight size={18}/></button> : <div className="prose"><Markdown>{m.content}</Markdown></div>}{m.sources.length > 0 && <div className="evidence"><span className="eyebrow">RETRIEVED EVIDENCE · {m.sources.length}</span>{m.sources.map(s => <SourceCard key={s.id} source={s}/>)}</div>}</div></article>)}{busy && <article className="message assistant"><div className="message-avatar"><Headphones size={17}/></div><div className="message-body"><div className="message-label">Lenny Growth Assistant <span className="draft-label">Provisional draft</span></div>{stream ? <div className="prose"><Markdown>{stream}</Markdown></div> : <div className="generating"><LoaderCircle size={16} className="animate-spin"/>{phase}</div>}{sources.length > 0 && <small className="stream-evidence">{sources.length} relevant passages retrieved</small>}</div></article>}<div ref={end}/></div>}
      </section>
      <div className="composer-area">{error && <div className="error-message" role="alert">{error}</div>}<form className="composer" onSubmit={e => { e.preventDefault(); void send(); }}><textarea aria-label="Ask about product and growth" value={question} maxLength={4000} disabled={busy} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} placeholder="What are you working through? Ask the archive…" rows={2}/><div className="composer-toolbar"><div className="composer-options"><label><Terminal size={14}/><select aria-label="Model provider" value={provider} disabled={busy} onChange={e => setProvider(e.target.value)}><option value="ollama">Ollama · Local</option><option value="anthropic" disabled={!health?.providers.anthropic}>Anthropic · Cloud</option></select></label><label><FileText size={14}/><select aria-label="Response format" value={mode} disabled={busy} onChange={e => setMode(e.target.value)}><option value="answer">Cited answer</option><option value="essay">Ship 30 essay</option><option value="html">HTML brief</option></select></label></div><button className="send-button" type="submit" aria-label="Send question" disabled={busy || !question.trim()}>{busy ? <LoaderCircle size={19} className="animate-spin"/> : <ArrowUp size={20}/>}</button></div></form><div className="composer-footer"><span><Check size={12}/> Every insight starts with a source</span><span>{latency !== null ? `${(latency / 1000).toFixed(1)}s to first token` : 'Enter to send · Shift + Enter for a new line'}</span></div>{provider === 'anthropic' && <p className="cloud-note">Cloud mode sends your question and retrieved excerpts to Anthropic.</p>}<div className="sr-only" aria-live="polite">{phase}</div></div>
    </main>
    {artifact && <ArtifactViewer key={artifact.id} artifact={artifact} close={() => setArtifact(null)}/>}
  </div>;
}
