import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { docsPage } from '../lib/links';

const CLASSES = [
  { name: 'public', note: 'any approved model' },
  { name: 'internal', note: 'the default class' },
  { name: 'confidential', note: 'e.g. an SSN or a card number' },
  { name: 'secret', note: 'only models you cleared for it' },
];

export default function ProofSection() {
  return (
    <Section id="proof" label="§04 · prove it" title={<>A refusal that explains itself, and <em>a log that proves it.</em></>} aside="output from the demo stack">
      <div className="split">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <p className="lede">
            Every request gets a data class: your org default, what the caller asserts (it can only raise the class) and what the detector finds in the text. A model registry decides which models and keys may serve each class.
          </p>
          <div className="ladder" role="list" aria-label="Data classes, lowest to highest">
            {CLASSES.map((c, i) => (
              <div key={c.name} className="ladder-step" data-level={i + 1} role="listitem">
                {c.name}
                <small>{c.note}</small>
              </div>
            ))}
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-2)' }}>
            <li><strong style={{ color: 'var(--ink)' }}>No silent fallback.</strong> If no approved model can serve a request, it is refused with a clear reason. It is never quietly sent somewhere else.</li>
            <li><strong style={{ color: 'var(--ink)' }}>The refusal explains itself.</strong> A policy block returns HTTP 446 with a plain-language sentence your user can read.</li>
            <li><strong style={{ color: 'var(--ink)' }}>Preview before you enforce.</strong> The policy preview shows the class, the verdict and the route a request would take, without sending anything upstream.</li>
          </ul>
          <a className="opa-btn" style={{ alignSelf: 'flex-start' }} href={docsPage('/core-concepts/policies-and-guardrails')} target="_blank" rel="noopener noreferrer">$ read the policy docs →</a>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          <CodeBlock title="a request with an SSN" tag="captured output">
            <span className="tok-dim">$ </span>{'curl -s -X POST $GATEWAY/v1/chat/completions \\\n    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \\\n    -d \'{"model":"openai/gpt-4o-mini","messages":[{"role":"user",\n         "content":"Customer SSN is 123-45-6789, draft a reply."}]}\'\n\n'}
            <span className="tok-bad">HTTP 446</span>{'\n'}
            <span className="tok-dim">x-openproxyai-policy-action: </span>{'block\n'}
            <span className="tok-dim">x-openproxyai-policy-reason: </span>{'pii_detected\n\n'}
            {'{\n  '}<span className="tok-key">"error"</span>{': '}<span className="tok-str">"policy_violation"</span>{',\n  '}
            <span className="tok-key">"detail"</span>{': '}<span className="tok-str">"Potential PII detected: ssn"</span>{',\n  '}
            <span className="tok-key">"reason_code"</span>{': '}<span className="tok-str">"pii_detected"</span>{',\n  '}
            <span className="tok-key">"explanation"</span>{': '}<span className="tok-str">"This request appears to contain personal or sensitive data that your organization's policy does not allow to be sent."</span>{',\n  '}
            <span className="tok-key">"triggered_rules"</span>{': ['}<span className="tok-str">"pii_detection"</span>{']\n}'}
          </CodeBlock>
          <CodeBlock title="policy preview · nothing is sent" tag="captured output, trimmed">
            <span className="tok-dim">POST /api/v1/policy/preview</span>{'\n{\n  '}
            <span className="tok-key">"verdict"</span>{': '}<span className="tok-str">"blocked_by_policy"</span>{',\n  '}
            <span className="tok-key">"data_class"</span>{': { '}<span className="tok-key">"class"</span>{': '}<span className="tok-str">"confidential"</span>{', '}<span className="tok-key">"source"</span>{': '}<span className="tok-str">"detected"</span>{', '}<span className="tok-key">"entities"</span>{': ['}<span className="tok-str">"ssn"</span>{'] },\n  '}
            <span className="tok-key">"policy"</span>{': { '}<span className="tok-key">"allowed"</span>{': '}<span className="tok-num">false</span>{', '}<span className="tok-key">"action"</span>{': '}<span className="tok-str">"block"</span>{' },\n  '}
            <span className="tok-key">"not_evaluated"</span>{': ['}<span className="tok-str">"rate_limit"</span>{', '}<span className="tok-str">"budget"</span>{', '}<span className="tok-str">"cache"</span>{', '}<span className="tok-str">"upstream"</span>{', ...]\n}'}
          </CodeBlock>
        </div>
      </div>
    </Section>
  );
}
