import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import Section from '../components/Section';
import { CardGrid, Shot, Steps } from '../components/blocks';
import ConsoleSection from '../sections/ConsoleSection';

const STAGES = [
  { title: 'Observe', body: 'Rules are evaluated, but nothing is blocked. Use it to see how your rules would behave before anyone is affected.' },
  { title: 'Log only', body: 'What would have been refused is recorded, and nothing is blocked. You see exactly what would have been stopped, and by which rule.' },
  { title: 'Enforce', body: 'Requests that break a rule are refused before they reach an AI model. The person is told why, and the decision is recorded.' },
];

const RULES = [
  { title: 'Approved models', body: 'Name the AI models, accounts and regions your organization may use for each level of sensitivity. A request no approved model can handle is refused with a reason, never rerouted.' },
  { title: 'Data protection', body: 'Each request gets a sensitivity level from your default, what the application says and what is detected in the text, such as a card or social security number. It can be stopped or cleaned before it leaves.' },
  { title: 'Blocked words and phrases', body: 'List the terms that must never be sent to an AI model, such as the name of a confidential project.' },
  { title: 'Manipulation attempts', body: 'Tricks aimed at the AI itself, such as hidden instructions in a document, are screened before they reach the model.' },
  { title: 'Answer checks', body: 'Screen and redact what comes back from the model, so sensitive details do not reach the person who should not see them.' },
  { title: 'Approved tools for agents', body: 'Give each AI agent a short list of the actions it may take. Tools are locked once approved, and anything else is stopped before it happens.' },
];

const CHECKS = [
  { title: 'Who is asking', body: 'The request is matched to a person, an application or an AI agent your organization has registered.' },
  { title: 'Within limits', body: 'Budgets and rate limits by team and by model are checked before the request goes on.' },
  { title: 'What the rules say', body: 'It is compared with your policy: the approved models, the blocked terms, the sensitivity of the content.' },
  { title: 'Already answered', body: 'If you turned on answer reuse, a repeated question is answered from memory. Your policy is always applied first.' },
  { title: 'Which approved model', body: 'An approved model is chosen by sensitivity, region or measured quality, and traffic moves away from a provider in trouble.' },
  { title: 'Written down', body: 'It is allowed, cleaned of sensitive details, or stopped. Either way, a record is written.' },
];

const MORE = [
  { title: 'Budgets by team', body: 'Spend limits by team and by model, with what has been spent this month and where the month is heading.' },
  { title: 'Do not pay twice', body: 'Optional answer reuse: exact repeats, shared across servers, and similar questions. You turn it on when you are ready.' },
  { title: 'Know a change is better', body: 'Feedback, test sets, scoring, live experiments and an approval gate that makes a prompt pass its evaluation before it goes live.' },
  { title: 'Plugs into what you run', body: 'Usage and spend for your monitoring tools, OpenTelemetry traces and a security event for every block, sent to your SIEM. Off by default.' },
  { title: 'For your teams', body: 'Shared conversations, large batch jobs under the same rules and budget, and a workspace to try a prompt on several models at once.' },
  { title: 'Protected administration', body: 'Limits on sign-in attempts, restricted access to technical metrics, and only owners or administrators can revoke access keys.' },
];

export default function ProductPage() {
  useEffect(() => { document.title = 'Product | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product"
        title={<>One checkpoint for every <span style={{ color: 'var(--soft)' }}>AI request you make.</span></>}
        description="OpenProxyAI sits between your people, apps and AI agents and the AI models and tools they use. It applies your rules to every request and keeps a record of each decision. It runs in your own environment."
        secondary={{ label: 'See the rules', href: '#rules' }}
        visual={<Shot src="/images/console/dashboard.webp" alt="OpenProxyAI console dashboard: requests, cost, how many requests were stopped or flagged by policy, and the budget for the month." />}
      />
      <Section id="rollout" label="Start without disruption" title="Turn it on in three stages, at your own pace." aside="You do not have to block anything on day one. Watch first, then log, then enforce. A preview shows the decision for any sample request before you switch anything on.">
        <CardGrid items={STAGES} min={280} />
      </Section>
      <Section id="rules" label="The rules you set" title="What the checkpoint can allow, stop, clean up and limit.">
        <CardGrid items={RULES} />
      </Section>
      <ConsoleSection eyebrow="The console" title="Everything your team sees, on real screens." lede="These are screens from the OpenProxyAI console, shown with sample data." />
      <Section id="path" label="One request, start to finish" title="The same checks, every time.">
        <Steps items={CHECKS} />
      </Section>
      <Section id="more" label="Alongside it" title="And what runs next to the checkpoint." aside="Included in every plan. Plans only change the limits on users, keys and audit history.">
        <CardGrid items={MORE} />
      </Section>
      <PageCta title="See your own rules stop a risky request." body="We will set a rule with your team, send a request through it, and open the record it leaves behind." />
    </>
  );
}
