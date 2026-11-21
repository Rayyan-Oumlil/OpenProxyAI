import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import Section from '../components/Section';
import SubProducts from '../components/SubProducts';
import { CardGrid, KeyValue, Shot, Steps } from '../components/blocks';

const DOES = [
  { title: 'Monitor in real time', body: 'The extension sees every prompt an employee types into a generative AI site, and every answer that comes back, as it happens in the browser.' },
  { title: 'Report PII sent to unauthorized AI', body: 'When personal information is sent to a generative AI service that your organization has not authorized, the extension reports it.' },
  { title: 'Redact and alert', body: 'The extension redacts sensitive data before it leaves the browser, and reports any upload of sensitive data to your security team.' },
];

const INSTALL = [
  { title: 'Package it for your organization', body: 'You get one extension build, tied to your OpenProxyAI environment, so every browser reports to your console and nowhere else.' },
  { title: 'Deploy it to employee desktops', body: 'Push it through the browser and device management you already use. Employees do not install anything and cannot quietly remove it.' },
  { title: 'It starts reporting', body: 'Each browser registers with your console. From the first prompt, activity is visible per person and per generative AI service.' },
];

const AUTHORIZED = [
  { k: 'Authorized services', v: 'The generative AI services your organization has approved. Sending data to them is allowed, and still monitored and redacted.' },
  { k: 'Everything else', v: 'Any other generative AI site is treated as unauthorized. If personal information is sent to one, it is reported as an incident.' },
  { k: 'You decide the list', v: 'Approve or remove a service in the console. The change reaches every browser without touching a single desktop.' },
];

const SECURITY_TEAM = [
  { k: 'PII sent to an unauthorized service', v: 'Who sent it, when, to which service, and what kind of personal information it was.' },
  { k: 'Upload of sensitive data', v: 'A file or text containing sensitive data that was uploaded to a generative AI service, reported as it happens.' },
  { k: 'What the extension redacted', v: 'Each redaction, so the team can see how often the protection acted and for whom.' },
];

const COVERAGE = [
  { k: 'Where it runs', v: 'In the desktop browsers where it is installed. That is why deploying it through device management matters.' },
  { k: 'What it cannot see', v: 'AI used in browsers without the extension, on personal devices, or in desktop apps that are not a browser. Pair it with the Central AI Proxy, which governs everything that reaches it.' },
];

export default function WebBrowserControlPage() {
  useEffect(() => { document.title = 'Web Browser Control | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product · Web Browser Control"
        title={<>A browser extension that watches <span style={{ color: 'var(--soft)' }}>AI use as it happens.</span></>}
        description="Install the OpenProxyAI extension on your employees' desktops. It monitors every prompt and every AI answer in real time, reports personal information sent to unauthorized generative AI, and redacts and reports sensitive uploads."
        secondary={{ label: 'What it does', href: '#does' }}
        visual={<Shot src="/images/console/logs.webp" alt="OpenProxyAI console request log: each request with the person, the model, the decision and the cost." />}
      />
      <Section id="does" label="What it does" title="Three jobs, running inside the browser." aside="The browser is where employees meet generative AI. This is the control that sits there with them.">
        <CardGrid items={DOES} min={260} />
      </Section>
      <Section id="install" label="Installing it" title="On every desktop, without asking anyone to do it." aside="Rollout is an IT task, not a training task.">
        <Steps items={INSTALL} min={260} />
      </Section>
      <Section id="authorized" label="Authorized and unauthorized AI" title="The extension knows which AI your company approved.">
        <KeyValue rows={AUTHORIZED} />
      </Section>
      <Section id="reports" label="For the security team" title="What lands in front of your security team." aside="Reports name the person, the service and the kind of data, so the team can act on them.">
        <KeyValue rows={SECURITY_TEAM} />
      </Section>
      <Section id="coverage" label="Honest limits" title="Where the extension runs, and where it does not.">
        <KeyValue rows={COVERAGE} />
      </Section>
      <SubProducts current="web-browser-control" />
      <PageCta title="See the extension catch a real prompt." body="We will install it on a test desktop, send a prompt with personal data to an unapproved AI site, and open the report your security team would receive." />
    </>
  );
}
