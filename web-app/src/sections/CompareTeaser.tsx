import { Link } from 'react-router-dom';
import Section from '../components/Section';

export default function CompareTeaser() {
  return (
    <Section id="compare-teaser" label="§07 · compare" title={<>Looking at <em>other gateways?</em> Good. Compare honestly.</>} aside="we say when another tool fits better">
      <div className="split" style={{ alignItems: 'center' }}>
        <p className="lede">
          We wrote a dated comparison for LiteLLM, Portkey, Helicone, Kong, Cloudflare, OpenRouter and LangChain. Each one says where OpenProxyAI differs and when the other tool is the better fit. Our edge is governance: data-class routing, bounded MCP tools and an audit trail you host.
        </p>
        <div><Link to="/compare" className="opa-btn">$ open the comparison hub →</Link></div>
      </div>
    </Section>
  );
}
