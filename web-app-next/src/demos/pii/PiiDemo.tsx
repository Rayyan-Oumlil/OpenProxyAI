import { useId, useState } from 'react';
import { MAX_INPUT, REDACTED, redact } from './redact';

const SAMPLE = 'Patient Jane Doe (jane.doe@clinic.org), SSN 123-45-6789, paid with 4111 1111 1111 1111. Summarize her visit.';

export default function PiiDemo() {
  const [text, setText] = useState(SAMPLE);
  const inputId = useId();
  const { output, hits } = redact(text);
  const parts = output.split(REDACTED);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div>
        <label htmlFor={inputId} className="text-step--1 font-medium text-ink-dim">Your prompt</label>
        <textarea
          id={inputId}
          value={text}
          maxLength={MAX_INPUT}
          onChange={e => setText(e.target.value.slice(0, MAX_INPUT))}
          rows={7}
          className="mt-2 w-full resize-y rounded-lg border border-line bg-surface p-4 font-mono text-step--1 text-ink outline-none focus:border-signal"
        />
        <p className="mt-1 text-right font-mono text-[11px] text-ink-dim">{text.length}/{MAX_INPUT}</p>
      </div>
      <div>
        <p className="text-step--1 font-medium text-ink-dim">What the model receives</p>
        <output htmlFor={inputId} aria-live="polite" className="mt-2 block min-h-[11rem] whitespace-pre-wrap break-words rounded-lg border border-line bg-surface p-4 font-mono text-step--1 text-ink">
          {parts.map((p, i) => (
            <span key={i}>
              {p}
              {i < parts.length - 1 && <mark className="rounded bg-signal/20 px-0.5 text-signal">{REDACTED}</mark>}
            </span>
          ))}
        </output>
        <p className="mt-2 font-mono text-[11px] text-ink-dim">
          email ×{hits.email} · ssn ×{hits.ssn} · card ×{hits.credit_card} — same patterns as <code>policy_service.py</code>
        </p>
      </div>
    </div>
  );
}
