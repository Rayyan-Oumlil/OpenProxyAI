import { useState } from "react";

type Language = "python" | "typescript" | "curl";

type StepStartUsingProps = {
  apiKey: string;
  onDismiss: () => void;
};

const LANGUAGES: { id: Language; label: string }[] = [
  { id: "python", label: "Python" },
  { id: "typescript", label: "TypeScript" },
  { id: "curl", label: "cURL" },
];

function buildSnippet(lang: Language, key: string): string {
  switch (lang) {
    case "python":
      return `# Python
import openproxy

client = openproxy.OpenProxy(api_key="${key}")
response = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)`;

    case "typescript":
      return `// TypeScript
import OpenProxy from 'openproxy-ai';

const client = new OpenProxy({ apiKey: '${key}' });
const response = await client.chat.completions.create({
  model: 'openai/gpt-4o',
  messages: [{ role: 'user', content: 'Hello!' }],
});
console.log(response.choices[0].message.content);`;

    case "curl":
      return `# cURL
curl ${import.meta.env.VITE_API_BASE_URL ?? "https://api.openproxyai.com"}/v1/chat/completions \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"openai/gpt-4o","messages":[{"role":"user","content":"Hello!"}]}'`;
  }
}

export function StepStartUsing({ apiKey, onDismiss }: StepStartUsingProps) {
  const [language, setLanguage] = useState<Language>("python");

  return (
    <div className="onboarding-step">
      <div className="onboarding-step-indicator">
        <span className="onboarding-dot onboarding-dot--done" />
        <span className="onboarding-dot onboarding-dot--done" />
        <span className="onboarding-dot onboarding-dot--active" />
      </div>

      <h2 className="onboarding-title">Start using OpenProxy</h2>
      <p className="onboarding-description">
        Drop this snippet into your project to send your first request.
      </p>

      <div className="onboarding-lang-tabs" role="tablist" aria-label="Language selector">
        {LANGUAGES.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={language === id}
            className={`onboarding-lang-tab${language === id ? " onboarding-lang-tab--active" : ""}`}
            onClick={() => setLanguage(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="onboarding-code-block" role="tabpanel">
        <pre>
          <code>{buildSnippet(language, apiKey)}</code>
        </pre>
      </div>

      <button type="button" onClick={onDismiss}>
        Dismiss
      </button>
    </div>
  );
}
