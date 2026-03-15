import type { ChatCompletionChunk, GatewayMeta } from '../types/chat.js';

function parseChunk(line: string): ChatCompletionChunk | null {
  if (!line.startsWith('data: ')) return null;
  const data = line.slice(6).trim();
  if (data === '[DONE]') return null;
  try {
    return JSON.parse(data) as ChatCompletionChunk;
  } catch {
    return null;
  }
}

export async function* streamSSE(
  response: Response,
  gateway: GatewayMeta,
): AsyncIterable<ChatCompletionChunk> {
  if (!response.body) throw new Error('No response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const chunk = parseChunk(line.trim());
        if (chunk) {
          yield { ...chunk, gateway };
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
