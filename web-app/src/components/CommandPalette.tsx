import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CALENDLY_URL } from '../lib/links';

interface PaletteItem {
  label: string;
  hint: string;
  action: (navigate: ReturnType<typeof useNavigate>) => void;
}

const ITEMS: PaletteItem[] = [
  { label: 'home', hint: '/', action: nav => nav('/') },
  { label: 'product', hint: '/product', action: nav => nav('/product') },
  { label: 'security', hint: '/security', action: nav => nav('/security') },
  { label: 'providers', hint: '/providers', action: nav => nav('/providers') },
  { label: 'pricing', hint: '/pricing', action: nav => nav('/pricing') },
  { label: 'docs', hint: 'docs.openproxyai.com', action: () => window.open('https://docs.openproxyai.com', '_blank', 'noopener,noreferrer') },
  { label: 'book a demo', hint: 'calendly', action: () => window.open(CALENDLY_URL, '_blank', 'noopener,noreferrer') },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const filtered = ITEMS.filter(i => i.label.includes(query.toLowerCase()));

  function openPalette() {
    setQuery('');
    setSelected(0);
    setOpen(true);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (open) setOpen(false);
        else openPalette();
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  function onQueryChange(next: string) {
    setQuery(next);
    setSelected(0);
  }

  function runItem(item: PaletteItem) {
    item.action(navigate);
    setOpen(false);
  }

  function onInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelected(s => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelected(s => Math.max(s - 1, 0));
    } else if (e.key === 'Enter' && filtered[selected]) {
      runItem(filtered[selected]);
    }
  }

  return (
    <>
      <button
        onClick={openPalette}
        aria-label="Open command palette"
        style={{
          display: 'flex', alignItems: 'center', gap: 6, background: 'var(--panel)',
          border: '1px solid var(--line-2)', borderRadius: 6, padding: '5px 9px',
          color: 'var(--ink-3)', fontFamily: 'var(--mono)', fontSize: 11.5, cursor: 'pointer',
          transition: 'border-color 0.12s, color 0.12s',
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--line-2)'; e.currentTarget.style.color = 'var(--ink-3)'; }}
      >
        <span>search</span>
        <kbd style={{ fontFamily: 'var(--mono)', fontSize: 10.5, opacity: 0.8 }}>⌘K</kbd>
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(4,5,7,0.7)', backdropFilter: 'blur(2px)',
            zIndex: 200, display: 'flex', justifyContent: 'center', paddingTop: '14vh',
          }}
        >
          <div
            className="opa-card"
            onClick={e => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 540, height: 'fit-content', overflow: 'hidden' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', borderBottom: '1px solid var(--line)' }}>
              <span style={{ color: 'var(--accent)', fontFamily: 'var(--mono)', fontSize: 14 }}>$</span>
              <input
                ref={inputRef}
                value={query}
                onChange={e => onQueryChange(e.target.value)}
                onKeyDown={onInputKeyDown}
                placeholder="jump to…"
                style={{
                  flex: 1, background: 'transparent', border: 'none', outline: 'none',
                  color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 14,
                }}
              />
              <kbd style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-3)' }}>esc</kbd>
            </div>

            <div style={{ maxHeight: 320, overflow: 'auto', padding: 6 }}>
              {filtered.length === 0 && (
                <div style={{ padding: '18px 12px', color: 'var(--ink-3)', fontSize: 13 }}>no matches</div>
              )}
              {filtered.map((item, i) => (
                <div
                  key={item.label}
                  onMouseEnter={() => setSelected(i)}
                  onClick={() => runItem(item)}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 12px', borderRadius: 6, cursor: 'pointer',
                    background: selected === i ? 'var(--panel-2)' : 'transparent',
                    borderLeft: selected === i ? '2px solid var(--accent)' : '2px solid transparent',
                  }}
                >
                  <span style={{ color: 'var(--ink)', fontSize: 13.5 }}>{item.label}</span>
                  <span style={{ color: 'var(--ink-3)', fontSize: 11.5, fontFamily: 'var(--mono)' }}>{item.hint}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
