import CodeTabs from '../../components/CodeTabs';
import Section from '../../components/Section';

const TABS = [
  { label: 'Python', code: `from openai import OpenAI

client = OpenAI(
    api_key="opai_...",
    base_url="https://gateway.your-company.com/v1",
)
client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])` },
  { label: 'TypeScript', code: `import OpenAI from 'openai';

const client = new OpenAI({
  apiKey: 'opai_...',
  baseURL: 'https://gateway.your-company.com/v1',
});
await client.chat.completions.create({ model: 'claude-sonnet', messages: [{ role: 'user', content: 'Hi' }] });` },
  { label: 'curl', code: `curl https://gateway.your-company.com/v1/chat/completions \\
  -H "Authorization: Bearer opai_..." \\
  -H "x-openproxy-labels: team=finance" \\
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Hi"}]}'` },
];

export default function DropIn() {
  return (
    <Section title="Change one line. Keep your SDK." lede="OpenAI-compatible endpoints: point base_url at the gateway and every call is governed.">
      <CodeTabs tabs={TABS} />
    </Section>
  );
}
