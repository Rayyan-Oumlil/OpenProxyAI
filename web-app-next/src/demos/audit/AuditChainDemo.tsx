import { useEffect, useState } from 'react';
import { SAMPLE_ENTRIES, buildChain, verifyChain, type ChainLink } from './chain';

interface ChainState { links: ChainLink[]; valid: boolean[] }

async function freshChain(): Promise<ChainState> {
  const links = await buildChain(SAMPLE_ENTRIES);
  return { links, valid: await verifyChain(links) };
}

export default function AuditChainDemo() {
  const [chain, setChain] = useState<ChainState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    freshChain().then(
      c => { if (!cancelled) setChain(c); },
      (e: unknown) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); },
    );
    return () => { cancelled = true; };
  }, []);

  async function reset() {
    try {
      setChain(await freshChain());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function tamper(index: number, action: string) {
    if (!chain) return;
    const links = chain.links.map((l, i) => (i === index ? { ...l, entry: { ...l.entry, action } } : l));
    // Show the edit immediately; apply verification only if no newer edit replaced these links.
    setChain({ links, valid: chain.valid });
    const valid = await verifyChain(links);
    setChain(current => (current?.links === links ? { links, valid } : current));
  }

  if (error) return <p role="alert" className="text-danger">Audit demo unavailable: {error}. It needs Web Crypto (HTTPS).</p>;
  if (!chain) return <p className="font-mono text-step--1 text-ink-dim">hashing…</p>;

  return (
    <div>
      <ol className="space-y-2">
        {chain.links.map((l, i) => (
          <li key={l.entry.seq} className={`rounded-lg border p-3 font-mono text-step--1 ${chain.valid[i] ? 'border-line bg-surface' : 'border-danger bg-danger/10'}`}>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="text-ink-dim">#{l.entry.seq}</span>
              <span className="text-ink">{l.entry.actor}</span>
              <label className="flex flex-1 items-center gap-2">
                <span className="sr-only">Action for entry {l.entry.seq}</span>
                <input
                  value={l.entry.action}
                  onChange={e => void tamper(i, e.target.value)}
                  className="min-w-0 flex-1 rounded border border-line bg-bg px-2 py-1 text-ink outline-none focus:border-signal"
                />
              </label>
              <span className={chain.valid[i] ? 'text-ok' : 'text-danger'}>{chain.valid[i] ? '✓ verified' : '✗ broken'}</span>
            </div>
            <p className="mt-1 truncate text-[11px] text-ink-dim">prev {l.prevHash.slice(0, 16)}… → hash {l.hash.slice(0, 16)}…</p>
          </li>
        ))}
      </ol>
      <button onClick={() => void reset()} className="mt-4 rounded-md border border-line px-3 py-1.5 font-mono text-step--1 text-ink-dim hover:text-ink">
        Reset chain
      </button>
    </div>
  );
}
