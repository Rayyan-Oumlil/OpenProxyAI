import React, {useState} from 'react';
import Layout from '@theme/Layout';
import Head from '@docusaurus/Head';
import Link from '@docusaurus/Link';
import styles from './llm-cost-calculator.module.css';

interface Field {
  id: string;
  label: string;
  hint: string;
  value: number;
  step: number;
  min: number;
  max?: number;
}

const DAYS_PER_MONTH = 30;
const HEADROOM = 0.25;

const DEFAULTS: readonly Field[] = [
  {id: 'requests', label: 'Requests per day', hint: 'All teams and apps combined', value: 20000, step: 100, min: 0},
  {id: 'inTokens', label: 'Average input tokens per request', hint: 'Prompt plus context', value: 1200, step: 50, min: 0},
  {id: 'outTokens', label: 'Average output tokens per request', hint: 'The model answer', value: 350, step: 10, min: 0},
  {id: 'priceIn', label: 'Input price (USD per 1M tokens)', hint: 'Use your provider price list', value: 3, step: 0.1, min: 0},
  {id: 'priceOut', label: 'Output price (USD per 1M tokens)', hint: 'Use your provider price list', value: 15, step: 0.1, min: 0},
  {id: 'cacheHit', label: 'Share answered from cache (%)', hint: 'Repeated questions, FAQ-style traffic', value: 15, step: 1, min: 0, max: 100},
  {id: 'teams', label: 'Number of teams', hint: 'For a per-team budget starting point', value: 6, step: 1, min: 1},
];

type Values = Record<string, number>;

const money = (n: number): string =>
  n.toLocaleString('en-US', {style: 'currency', currency: 'USD', maximumFractionDigits: 0});

function compute(v: Values) {
  const monthlyRequests = v.requests * DAYS_PER_MONTH;
  const perRequest = (v.inTokens * v.priceIn + v.outTokens * v.priceOut) / 1_000_000;
  const monthly = monthlyRequests * perRequest;
  const hit = Math.min(Math.max(v.cacheHit, 0), 100) / 100;
  const savings = monthly * hit;
  const teams = Math.max(1, Math.round(v.teams));
  return {
    monthlyRequests,
    perRequest,
    monthly,
    savings,
    afterCache: monthly - savings,
    perTeam: (monthly / teams) * (1 + HEADROOM),
  };
}

export default function LlmCostCalculator(): React.JSX.Element {
  const [values, setValues] = useState<Values>(() =>
    Object.fromEntries(DEFAULTS.map((f) => [f.id, f.value])),
  );
  const out = compute(values);

  const update = (id: string, raw: string) => {
    const n = Number(raw);
    setValues((prev) => ({...prev, [id]: Number.isFinite(n) ? n : 0}));
  };

  const title = 'LLM cost calculator: estimate your monthly AI spend and team budgets';
  const description =
    'Free LLM cost calculator. Enter your request volume, token counts and provider prices to estimate monthly spend, the effect of caching and a starting budget per team.';

  return (
    <Layout title="LLM cost calculator" description={description}>
      <Head>
        <meta property="og:title" content={title} />
        <meta property="og:description" content={description} />
        <script type="application/ld+json">
          {JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebApplication',
            name: 'LLM cost calculator',
            applicationCategory: 'BusinessApplication',
            operatingSystem: 'Any',
            offers: {'@type': 'Offer', price: '0', priceCurrency: 'USD'},
            url: 'https://docs.openproxyai.com/tools/llm-cost-calculator',
          })}
        </script>
      </Head>
      <main className={styles.page}>
        <div className={styles.wrap}>
          <h1 className={styles.title}>LLM cost calculator</h1>
          <p className={styles.lede}>
            Estimate what your AI traffic costs per month, how much a cache could save, and a sensible starting
            budget for each team. Everything runs in your browser. Nothing is sent anywhere.
          </p>

          <div className={styles.grid}>
            <form className={styles.card} onSubmit={(e) => e.preventDefault()} aria-label="Cost inputs">
              <h2 className={styles.h2}>Your traffic</h2>
              {DEFAULTS.map((f) => (
                <div className={styles.field} key={f.id}>
                  <label htmlFor={f.id}>{f.label}</label>
                  <input
                    id={f.id}
                    type="number"
                    inputMode="decimal"
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    value={values[f.id]}
                    onChange={(e) => update(f.id, e.target.value)}
                    aria-describedby={`${f.id}-hint`}
                  />
                  <span id={`${f.id}-hint`} className={styles.hint}>
                    {f.hint}
                  </span>
                </div>
              ))}
              <p className={styles.note}>
                The values above are examples, not current prices. Replace them with your own volumes and your
                provider's price list.
              </p>
            </form>

            <section className={styles.card} aria-live="polite" aria-label="Estimated cost">
              <h2 className={styles.h2}>Estimate</h2>
              <dl className={styles.results}>
                <div>
                  <dt>Cost per request</dt>
                  <dd>{out.perRequest < 0.01 ? `$${out.perRequest.toFixed(4)}` : `$${out.perRequest.toFixed(3)}`}</dd>
                </div>
                <div>
                  <dt>Requests per month</dt>
                  <dd>{out.monthlyRequests.toLocaleString('en-US')}</dd>
                </div>
                <div className={styles.big}>
                  <dt>Monthly spend</dt>
                  <dd>{money(out.monthly)}</dd>
                </div>
                <div>
                  <dt>Saved by caching</dt>
                  <dd>{money(out.savings)}</dd>
                </div>
                <div>
                  <dt>Spend after caching</dt>
                  <dd>{money(out.afterCache)}</dd>
                </div>
                <div>
                  <dt>Starting budget per team</dt>
                  <dd>{money(out.perTeam)}</dd>
                </div>
              </dl>
              <p className={styles.note}>
                Assumes {DAYS_PER_MONTH} days a month, traffic split evenly across teams, and {Math.round(HEADROOM * 100)}%
                headroom on the team budget. Real traffic is uneven, so treat the team figure as a first guess and
                adjust after a week of data.
              </p>
            </section>
          </div>

          <section className={styles.next}>
            <h2 className={styles.h2}>Turn the estimate into limits</h2>
            <p>
              A number on a page does not stop a runaway loop. OpenProxyAI enforces the budget: set a monthly
              budget per team, add request and token limits, and see spend by team and model as it happens.
            </p>
            <ul>
              <li>
                <Link to="/core-concepts/rate-limiting-and-budgets">Rate limits and budgets</Link>
              </li>
              <li>
                <Link to="/core-concepts/caching">Caching: exact and semantic</Link>
              </li>
              <li>
                <Link to="/blog/know-who-spends-what-on-ai">Know who spends what on AI</Link>
              </li>
              <li>
                <Link to="/getting-started/quickstart">Run it yourself in minutes</Link>
              </li>
            </ul>
          </section>
        </div>
      </main>
    </Layout>
  );
}
