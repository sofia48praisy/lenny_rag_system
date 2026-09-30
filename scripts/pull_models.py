"""Download models through the local Ollama API with compact progress output."""
import json
import time
import urllib.request

for model in ['nomic-embed-text', 'llama3.2:3b']:
    request = urllib.request.Request('http://127.0.0.1:11434/api/pull',
                                     data=json.dumps({'model': model, 'stream': True}).encode(),
                                     headers={'Content-Type': 'application/json'})
    last = 0
    with urllib.request.urlopen(request, timeout=600) as response:
        for line in response:
            event = json.loads(line)
            if event.get('error'):
                raise RuntimeError(event['error'])
            if time.monotonic() - last > 15 or event.get('status') == 'success':
                print(model, event.get('status'), f"{event.get('completed', 0) // 1048576}/{event.get('total', 0) // 1048576} MB", flush=True)
                last = time.monotonic()
