export interface AuditEntry { seq: number; actor: string; action: string; model: string; status: number }
export interface ChainLink { entry: AuditEntry; prevHash: string; hash: string }

export const GENESIS = '0'.repeat(64);

export const SAMPLE_ENTRIES: AuditEntry[] = [
  { seq: 1, actor: 'finance-app', action: 'chat.completion', model: 'claude-sonnet', status: 200 },
  { seq: 2, actor: 'support-bot', action: 'chat.completion', model: 'gpt-4o-mini', status: 200 },
  { seq: 3, actor: 'research-agent', action: 'tool.call github.search', model: '—', status: 200 },
  { seq: 4, actor: 'ops-agent', action: 'tool.call postgres.query', model: '—', status: 446 },
  { seq: 5, actor: 'finance-app', action: 'chat.completion', model: 'azure-gpt-4o', status: 402 },
];

export function canonicalJson(e: AuditEntry): string {
  const keys = Object.keys(e).sort() as (keyof AuditEntry)[];
  return JSON.stringify(Object.fromEntries(keys.map(k => [k, e[k]])));
}

export async function sha256Hex(s: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
}

function linkHash(prevHash: string, entry: AuditEntry): Promise<string> {
  return sha256Hex(prevHash + canonicalJson(entry));
}

export async function buildChain(entries: AuditEntry[]): Promise<ChainLink[]> {
  const links: ChainLink[] = [];
  for (const entry of entries) {
    const prevHash = links.at(-1)?.hash ?? GENESIS;
    links.push({ entry, prevHash, hash: await linkHash(prevHash, entry) });
  }
  return links;
}

export async function verifyChain(links: ChainLink[]): Promise<boolean[]> {
  const result: boolean[] = [];
  for (const [i, link] of links.entries()) {
    const expectedPrev = i === 0 ? GENESIS : links[i - 1].hash;
    const prevOk = i === 0 ? true : result[i - 1];
    const selfOk = link.prevHash === expectedPrev && link.hash === (await linkHash(link.prevHash, link.entry));
    result.push(prevOk && selfOk);
  }
  return result;
}
