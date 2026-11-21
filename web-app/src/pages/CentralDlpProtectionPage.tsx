import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import Section from '../components/Section';
import SubProducts from '../components/SubProducts';
import { CardGrid, KeyValue, Shot, Steps } from '../components/blocks';

const PATHS = [
  { title: 'Path 1: ingest your sensitive data', body: 'Upload the documents you must protect. They are read, including scanned pages, and stored in one searchable database.' },
  { title: 'Path 2: compare every prompt to it', body: 'When someone sends a prompt out, it is compared by meaning against that database. A positive match is reported as possibly containing sensitive data.' },
];

const INGEST = [
  { title: 'Upload documents', body: 'Add the files that hold your sensitive information, such as contracts, customer lists, source code descriptions and internal reports. PDF is supported.' },
  { title: 'Read scanned pages', body: 'Optical character recognition (OCR) turns scanned documents and images of text into text, so a photographed page is protected like a typed one.' },
  { title: 'Store it in one database', body: 'Everything goes into the same vector database, so the documents you added last year and today are searched together.' },
];

const MATCH = [
  { title: 'A prompt is about to go out', body: 'Someone types a prompt, or uploads text, that would leave for a generative AI service on the internet.' },
  { title: 'It is searched by meaning', body: 'The prompt is compared with the vector database using semantic search. It looks for similar meaning, not just identical words, so a reworded copy can still be found.' },
  { title: 'A match is reported', body: 'If the search is positive, the prompt is reported as possibly containing sensitive data, so your security team can review it.' },
];

const ALSO = [
  { k: 'Personal data patterns', v: 'Email addresses, US Social Security numbers and payment card numbers are detected directly, with checks that keep false alarms down.' },
  { k: 'Your blocked terms', v: 'Words and phrases you list, such as a project code name, are caught on the way out.' },
  { k: 'Answers coming back', v: 'The same detectors can redact sensitive details in what a model sends back.' },
];

const LIMITS = [
  { k: 'A match is a signal, not proof', v: 'Similar meaning is not the same as the same data. A positive result says the prompt may include sensitive data, and a person decides what to do about it.' },
  { k: 'Your database is sensitive too', v: 'It holds the documents you most want to protect, so it runs in your own environment, with access limited to the people who manage it.' },
  { k: 'Only as good as what you ingest', v: 'The semantic search can only recognize what has been added to the database. Keep ingesting as new sensitive documents are created.' },
];

export default function CentralDlpProtectionPage() {
  useEffect(() => { document.title = 'Central DLP Protection | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product · Central DLP Protection"
        title={<>Teach it what is sensitive, <span style={{ color: 'var(--soft)' }}>then let it watch every prompt.</span></>}
        description="Central DLP Protection works in two paths. First you ingest your documents, scanned ones included, into one database. Then every prompt on its way to the internet is searched against it, and a positive match is reported."
        secondary={{ label: 'The two paths', href: '#paths' }}
        visual={<Shot src="/images/console/trace.webp" alt="OpenProxyAI request record: a request blocked because personal data was detected, what the caller was told, and the record number." />}
      />
      <Section id="paths" label="Two paths" title="One database that you fill, and one search that runs on every prompt.">
        <CardGrid items={PATHS} min={300} />
      </Section>
      <Section id="ingest" label="Path 1 · Ingest" title="Put your sensitive data into the database." aside="You choose what counts as sensitive by choosing what you add.">
        <Steps items={INGEST} min={260} />
      </Section>
      <Section id="match" label="Path 2 · Match" title="Compare every outgoing prompt against it." aside="This is a semantic search over a vector database, run on the prompt before it reaches the internet.">
        <Steps items={MATCH} min={260} />
      </Section>
      <Section id="also" label="Alongside it" title="The direct detectors still run.">
        <KeyValue rows={ALSO} />
      </Section>
      <Section id="limits" label="Honest limits" title="What a semantic match can and cannot tell you.">
        <KeyValue rows={LIMITS} />
      </Section>
      <SubProducts current="central-dlp-protection" />
      <PageCta title="See your own document catch a prompt." body="Bring a sample sensitive document. We will ingest it, send a reworded prompt that draws on it, and open the report your security team would receive." />
    </>
  );
}
