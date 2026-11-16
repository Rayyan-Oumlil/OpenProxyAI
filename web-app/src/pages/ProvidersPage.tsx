import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import CodeBlock from '../components/CodeBlock';
import ModelCatalogSection from '../sections/ModelCatalogSection';
import FailoverSection from '../sections/FailoverSection';

function ProviderKeyVisual() {
  return (
    <CodeBlock title="a provider key carries the rules" tag="fields from the API">
      <span className="tok-key">provider</span>{'        openai\n'}
      <span className="tok-key">region</span>{'          us | eu | ap | global\n'}
      <span className="tok-key">max_data_class</span>{'  internal | confidential | ...\n'}
      <span className="tok-key">weight</span>{'          share of traffic among healthy keys\n'}
      <span className="tok-key">api_base</span>{'        optional custom endpoint'}
    </CodeBlock>
  );
}

export default function ProvidersPage() {
  useEffect(() => { document.title = 'Providers and models | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Providers"
        title={<>One API. <span style={{ color: 'var(--accent)' }}>Your rules</span> for every model.</>}
        description="Use hosted providers and your own endpoints through one OpenAI-compatible gateway. Each provider key carries its region and the highest data class it may serve."
        visual={<ProviderKeyVisual />}
      />
      <ModelCatalogSection />
      <FailoverSection />
    </>
  );
}
