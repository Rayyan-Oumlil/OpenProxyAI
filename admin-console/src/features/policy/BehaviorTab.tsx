import { BehaviorControls } from "../../components/BehaviorControls";
import type { PolicyConfigRequest } from "../../api/types";

type SetForm = (update: (form: PolicyConfigRequest) => PolicyConfigRequest) => void;

export function BehaviorTab({ form, setForm, isAdmin }: { form: PolicyConfigRequest; setForm: SetForm; isAdmin: boolean }) {
  return (
    <>
      <section className="surface-panel stack-form" aria-labelledby="behavior-defaults-h">
        <h2 id="behavior-defaults-h" style={{ fontSize: "1rem", fontWeight: 600 }}>
          Defaults
        </h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          What a call is like when the caller does not say. Callers ask for behaviour with the <code>x-openproxy-behavior</code> header or a <code>behavior</code> field, in terms that do not depend on the
          provider; the gateway turns them into the parameters each model accepts. A caller's own <code>temperature</code>, <code>max_tokens</code> or <code>reasoning_effort</code> always wins over a default.
        </p>
        <BehaviorControls
          value={form.behavior_defaults ?? {}}
          onChange={(next) => setForm((f) => ({ ...f, behavior_defaults: next }))}
          disabled={!isAdmin}
          noneLabel="No default"
        />
      </section>

      <section className="surface-panel stack-form" aria-labelledby="behavior-ceiling-h">
        <h2 id="behavior-ceiling-h" style={{ fontSize: "1rem", fontWeight: 600 }}>
          Ceiling
        </h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          The most a caller may ask for. A request above it is lowered to it and the response says so (<code>X-OpenProxyAI-Behavior-Clamped</code>). The ceiling also lowers a caller's own{" "}
          <code>temperature</code>, <code>max_tokens</code> and <code>reasoning_effort</code>, so a raw parameter cannot walk around it. With no ceiling set, raw parameters are never touched.
        </p>
        <BehaviorControls
          value={form.behavior_ceiling ?? {}}
          onChange={(next) => setForm((f) => ({ ...f, behavior_ceiling: next }))}
          withCitations={false}
          disabled={!isAdmin}
          noneLabel="No ceiling"
        />
      </section>
    </>
  );
}
