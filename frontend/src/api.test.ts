import { describe, expect, it } from 'vitest';
import { readEvents } from './api';

function response(parts: string[]) {
  return new Response(new ReadableStream({ start(controller) {
    for (const p of parts) controller.enqueue(new TextEncoder().encode(p));
    controller.close();
  } }));
}
describe('SSE protocol', () => {
  it('handles network-fragmented frames', async () => {
    const events: unknown[] = [];
    await readEvents(response(['event: tok', 'en\ndata: {"text":"hello"}\n', '\nevent: done\ndata: {}\n\n']), (name, data) => events.push([name, data]));
    expect(events).toEqual([['token', { text: 'hello' }], ['done', {}]]);
  });
  it('rejects incomplete streams', async () => {
    await expect(readEvents(response(['event: token\ndata: {"text":"partial"}\n\n']), () => {})).rejects.toThrow('before completion');
  });
  it('surfaces server errors', async () => {
    await expect(readEvents(response(['event: error\ndata: {"detail":"Model offline"}\n\n']), () => {})).rejects.toThrow('Model offline');
  });
});
