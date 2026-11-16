import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { GITHUB_URL } from '../lib/links';

const COMMANDS = `git clone ${GITHUB_URL}
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build`;

export default function VerifySection() {
  return (
    <Section id="verify" label="Verify it yourself" title={<>Do not take our word. <em>Test it.</em></>} aside="for your security team">
      <div className="split">
        <p className="lede">
          Ask your engineers to run the demo. It sets up a sample organization, sends allowed, reused and blocked requests, and opens the console. Send a prompt with a social security number, watch your policy refuse it, then read the code that did it. The automated tests are in the repository.
        </p>
        <CodeBlock title="terminal" copy={COMMANDS}>
          <span className="tok-dim">$ </span>{COMMANDS.replace(/\n/g, '\n$ ')}
        </CodeBlock>
      </div>
    </Section>
  );
}
