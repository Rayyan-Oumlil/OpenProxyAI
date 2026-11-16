import { Link } from 'react-router-dom';
import Section from '../components/Section';

export default function CompareTeaser() {
  return (
    <Section id="compare-teaser" label="Compare" title={<>Looking at other options? <em>Compare honestly.</em></>} aside="we say when another tool fits better">
      <div className="split" style={{ alignItems: 'center' }}>
        <p className="lede">
          We wrote a dated comparison for LiteLLM, Portkey, Helicone, Kong, Cloudflare, OpenRouter and LangChain. Each one says where OpenProxyAI differs and when the other tool is the better fit. Our focus is governance you host yourself: sensitive data kept where you allow, controlled AI agents and a permanent record.
        </p>
        <div><Link to="/compare" className="opa-btn">$ open the comparison hub →</Link></div>
      </div>
    </Section>
  );
}
