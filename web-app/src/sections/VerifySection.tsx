import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { GITHUB_URL } from '../lib/links';

const COMMANDS = `git clone ${GITHUB_URL}
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build`;

export default function VerifySection() {
  return (
    <Section id="verify" label="§07 · verify it yourself" title={<>Don’t trust this page. <em>Run it.</em></>} aside="the demo needs only docker">
      <div className="split">
        <p className="lede">
          The demo seeds an organization, sends allowed, cached and blocked requests, and opens a console. Look at the request trace, send a prompt with an SSN and watch policy refuse it, then read the code that did it. Backend tests live in <code>backend/tests</code> and run with pytest.
        </p>
        <CodeBlock title="terminal" copy={COMMANDS}>
          <span className="tok-dim">$ </span>{COMMANDS.replace(/\n/g, '\n$ ')}
        </CodeBlock>
      </div>
    </Section>
  );
}
