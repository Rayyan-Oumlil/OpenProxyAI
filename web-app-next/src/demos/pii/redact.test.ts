import { describe, expect, it } from 'vitest';
import { MAX_INPUT, REDACTED, redact } from './redact';

describe('redact (mirrors backend PolicyService._EMAIL_RE/_SSN_RE/_CC_RE)', () => {
  it.each([
    ['contact jane.doe+ops@acme.co now', `contact ${REDACTED} now`, { email: 1, ssn: 0, credit_card: 0 }],
    ['ssn 123-45-6789 on file', `ssn ${REDACTED} on file`, { email: 0, ssn: 1, credit_card: 0 }],
    ['card 4111 1111 1111 1111 exp', `card ${REDACTED} exp`, { email: 0, ssn: 0, credit_card: 1 }],
    ['card 4111-1111-1111-1111', `card ${REDACTED}`, { email: 0, ssn: 0, credit_card: 1 }],
  ])('redacts %s', (input, output, hits) => {
    expect(redact(input)).toEqual({ output, hits });
  });

  it('leaves phone numbers alone (the backend has no phone pattern)', () => {
    expect(redact('call 514-555-1234').output).toBe('call 514-555-1234');
  });

  it('applies email, then SSN, then card — like the backend', () => {
    const r = redact('a@b.io 123-45-6789 4111111111111111');
    expect(r.output).toBe(`${REDACTED} ${REDACTED} ${REDACTED}`);
    expect(r.hits).toEqual({ email: 1, ssn: 1, credit_card: 1 });
  });

  it('is stable across repeated calls (no global-regex lastIndex leaks)', () => {
    expect(redact('x 123-45-6789').output).toBe(redact('x 123-45-6789').output);
  });

  it('handles a worst-case paste quickly', () => {
    const nasty = '1 2 3 4 5 6 7 8 9 0 '.repeat(MAX_INPUT / 20) + '🙂'.repeat(10);
    const t0 = performance.now();
    redact(nasty.slice(0, MAX_INPUT));
    expect(performance.now() - t0).toBeLessThan(50);
  });
});
