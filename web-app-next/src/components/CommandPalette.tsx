import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { NAV } from '../site/nav';
import { GITHUB_URL, DOCS_URL } from '../site/links';

type Navigate = ReturnType<typeof useNavigate>;
interface PaletteItem { label: string; hint: string; run: (navigate: Navigate) => void }

const ITEMS: PaletteItem[] = [
  { label: 'Home', hint: '/', run: nav => nav('/') },
  ...NAV.map(n => ({ label: n.label, hint: n.to, run: (nav: Navigate) => nav(n.to) })),
  { label: 'Docs', hint: 'docs.openproxyai.com', run: () => window.open(DOCS_URL, '_blank', 'noopener,noreferrer') },
  { label: 'GitHub', hint: 'source code', run: () => window.open(GITHUB_URL, '_blank', 'noopener,noreferrer') },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(o => !o);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Mounting the dialog per open gives it fresh query/selection state.
  return open ? <PaletteDialog onClose={() => setOpen(false)} /> : null;
}

function PaletteDialog({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const navigate = useNavigate();
  const filtered = ITEMS.filter(i => i.label.toLowerCase().includes(query.toLowerCase()));

  function choose(item: PaletteItem | undefined) {
    if (!item) return;
    item.run(navigate);
    onClose();
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Command palette" className="fixed inset-0 z-50 flex items-start justify-center bg-bg/70 p-4 pt-[15vh]" onClick={onClose}>
      <div className="w-full max-w-lg overflow-hidden rounded-lg border border-line bg-surface" onClick={e => e.stopPropagation()}>
        <input
          autoFocus
          value={query}
          onChange={e => { setQuery(e.target.value); setSelected(0); }}
          onKeyDown={e => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)); }
            if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
            if (e.key === 'Enter') choose(filtered[selected]);
          }}
          placeholder="Jump to…"
          aria-label="Search pages"
          className="w-full border-b border-line bg-transparent px-4 py-3 text-step-0 outline-none"
        />
        <ul role="listbox" aria-label="Results">
          {filtered.map((item, i) => (
            <li
              key={item.label}
              role="option"
              aria-selected={i === selected}
              onMouseEnter={() => setSelected(i)}
              onClick={() => choose(item)}
              className={`flex cursor-pointer justify-between px-4 py-2 text-step--1 ${i === selected ? 'bg-surface-2 text-ink' : 'text-ink-dim'}`}
            >
              <span>{item.label}</span>
              <span className="font-mono">{item.hint}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
