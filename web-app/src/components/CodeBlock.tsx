import { useState } from 'react';
import type { ReactNode } from 'react';
import { trackEvent } from '../lib/analytics';

interface CodeBlockProps {
  title: string;
  /** Short right-hand tag, e.g. the language or "captured output". */
  tag?: string;
  /** Plain text put on the clipboard. Omit for blocks that are not meant to be copied. */
  copy?: string;
  children: ReactNode;
}

export default function CodeBlock({ title, tag, copy, children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    if (!copy) return;
    try {
      await navigator.clipboard.writeText(copy);
      setCopied(true);
      trackEvent('copy_command', { block: title });
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard can be blocked (insecure context, permissions). The text stays selectable.
    }
  }

  return (
    <figure className="code" style={{ margin: 0 }}>
      <figcaption className="code-head">
        <span>{title}</span>
        {copy ? (
          <button type="button" className="code-copy" onClick={onCopy} aria-label={`Copy ${title}`}>
            {copied ? 'copied' : 'copy'}
          </button>
        ) : (
          tag && <span>{tag}</span>
        )}
      </figcaption>
      <pre>{children}</pre>
    </figure>
  );
}
