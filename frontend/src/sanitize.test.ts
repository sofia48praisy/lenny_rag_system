// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { safeArtifact } from './sanitize';

describe('artifact isolation', () => {
  it('removes executable content and external resource attributes', () => {
    const html = safeArtifact('<script>parent.alert(1)</script><img src="https://evil.test/pixel" onerror="alert(1)"><iframe src="https://evil.test"></iframe><a href="javascript:alert(1)">link</a><form action="https://evil.test"><input></form>');
    expect(html).not.toMatch(/<script|onerror|<iframe|<form|<input|javascript:|https:\/\/evil/);
    expect(html).toContain("script-src 'none'");
    expect(html).toContain("connect-src 'none'");
  });
  it('removes attacker policy and base URL while retaining safe layout', () => {
    const html = safeArtifact('<html><head><meta http-equiv="refresh" content="0;url=https://evil.test"><base href="https://evil.test"><style>h1{color:green}</style></head><body><h1>Growth brief</h1></body></html>');
    expect(html).not.toContain('evil.test');
    expect(html).not.toContain('http-equiv="refresh"');
    expect(html).toContain('Growth brief');
    expect(html).toContain('h1{color:green}');
  });
});
