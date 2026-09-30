export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}). Check the backend.`);
  }
  return response.json();
}

export async function readEvents(response: Response, onEvent: (event: string, data: unknown) => void) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  }
  if (!response.body) throw new Error('Streaming is unavailable');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', done = false;
  try {
    while (true) {
      const part = await reader.read();
      buffer += decoder.decode(part.value, { stream: !part.done }).replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const event = frame.split('\n').find(l => l.startsWith('event:'))?.slice(6).trim() ?? 'message';
        const raw = frame.split('\n').filter(l => l.startsWith('data:')).map(l => l.slice(5).trimStart()).join('\n');
        if (raw) {
          const data = JSON.parse(raw);
          if (event === 'error') throw new Error(data.detail);
          if (event === 'done') done = true;
          onEvent(event, data);
        }
      }
      if (part.done) break;
    }
    if (!done) throw new Error('Connection ended before completion. Reload the session to check whether the response was saved.');
  } finally { await reader.cancel(); reader.releaseLock(); }
}
