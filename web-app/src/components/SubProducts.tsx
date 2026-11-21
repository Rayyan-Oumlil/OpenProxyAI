import { Link } from 'react-router-dom';
import Section from './Section';
import { SUB_PRODUCTS, type SubProductSlug } from '../lib/subProducts';

interface SubProductsProps {
  /** Hide the product the visitor is already on. */
  current?: SubProductSlug;
  id?: string;
  label?: string;
  title?: string;
  aside?: string;
}

/** The three products under Product, as linked cards. */
export default function SubProducts({
  current,
  id = 'products',
  label = 'The product family',
  title = 'Three products, one policy.',
  aside = 'They share one set of rules, one console and one audit record. Open the one that closes your biggest gap.',
}: SubProductsProps) {
  const items = SUB_PRODUCTS.filter(p => p.slug !== current);
  return (
    <Section id={id} label={label} title={title} aside={aside}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))', gap: 20 }}>
        {items.map((p, i) => (
          <Link key={p.slug} to={p.href} className="opa-card" style={{ padding: 26, display: 'flex', flexDirection: 'column', gap: 12, textDecoration: 'none', color: 'inherit' }}>
            <span className="mono" style={{ fontSize: 13, color: 'var(--ink-3)' }}>{String(i + 1).padStart(2, '0')}</span>
            <h3 style={{ margin: 0, fontSize: 22, lineHeight: 1.2, fontWeight: 500, letterSpacing: '-0.02em' }}>{p.name}</h3>
            <p style={{ margin: 0, fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', textWrap: 'pretty' }}>{p.body}</p>
            <span style={{ marginTop: 'auto', paddingTop: 8, fontSize: 15, fontWeight: 500, textDecoration: 'underline', textUnderlineOffset: 3 }}>Learn more</span>
          </Link>
        ))}
      </div>
    </Section>
  );
}
