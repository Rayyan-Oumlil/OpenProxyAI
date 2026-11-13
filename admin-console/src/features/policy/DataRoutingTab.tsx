import { useId, useState } from "react";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";

import type { DataClass, PolicyConfigRequest, Rating, RoutingMode } from "../../api/types";
import { DATA_CLASSES, dataClassLabel } from "../../lib/dataClasses";
import { RoutingPreview } from "./RoutingPreview";

type SetForm = (update: (form: PolicyConfigRequest) => PolicyConfigRequest) => void;

/** The gateway's built-in view of what is sensitive, shown so an org knows what it is overriding. */
const BUILT_IN_CLASSES: { entity: string; cls: DataClass }[] = [
  { entity: "ssn", cls: "confidential" },
  { entity: "payment_card", cls: "confidential" },
  { entity: "email", cls: "internal" },
];

const ENTITY_NAME = /^[A-Za-z0-9_]{1,50}$/;
const MAX_MAP_ENTRIES = 50;

const MODES: { value: RoutingMode; title: string; detail: string }[] = [
  { value: "off", title: "Off", detail: "Requests are served as they are today. Nothing about models changes." },
  {
    value: "log_only",
    title: "Preview (log only)",
    detail: "Decide which registry model would serve each request and record it in the audit log, but never refuse anything. Use this to see the effect first.",
  },
  {
    value: "enforce",
    title: "Enforce",
    detail:
      "Only registry models cleared for a request's data class may serve it, each through its own provider key. A request nothing can serve is refused with HTTP 446. Needs at least one enabled model with an active provider key in the model registry.",
  },
];

const RISKS: { value: Rating; label: string }[] = [
  { value: "low", label: "Low risk only" },
  { value: "medium", label: "Up to medium risk" },
  { value: "high", label: "Any risk (up to high)" },
];

export function DataRoutingTab({
  form,
  setForm,
  isAdmin,
  unsaved,
  token,
}: {
  form: PolicyConfigRequest;
  setForm: SetForm;
  isAdmin: boolean;
  unsaved: boolean;
  token: string;
}) {
  const ids = { state: useId(), cls: useId(), entity: useId(), entityClass: useId(), risk: useId(), quality: useId(), qualityHelp: useId() };
  const map = form.data_class_map ?? {};
  const [entity, setEntity] = useState("");
  const [entityClass, setEntityClass] = useState<DataClass>("confidential");

  function addMapping() {
    const name = entity.trim();
    if (!ENTITY_NAME.test(name)) {
      toast.error("A name is letters, numbers and underscores, up to 50 characters, for example ssn or US_SSN.");
      return;
    }
    if (!(name in map) && Object.keys(map).length >= MAX_MAP_ENTRIES) {
      toast.error(`At most ${MAX_MAP_ENTRIES} entries.`);
      return;
    }
    setForm((f) => ({ ...f, data_class_map: { ...(f.data_class_map ?? {}), [name]: entityClass } }));
    setEntity("");
  }

  // Enter in this field adds the row; it must not fall through and save the whole policy.
  function onEnter(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      addMapping();
    }
  }

  function removeMapping(name: string) {
    setForm((f) => {
      const next = { ...(f.data_class_map ?? {}) };
      delete next[name];
      return { ...f, data_class_map: next };
    });
  }

  return (
    <>
      <section className="surface-panel stack-form">
        <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Data classes</h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          Every request is given a class, from public to secret: the highest of the default below, what the caller asserts in the
          x-openproxy-data-class header (it can only raise the class), and what is found in the text.
        </p>
        <label className="inline-control" htmlFor={ids.cls}>
          Default class
          <select
            id={ids.cls}
            value={form.default_data_class ?? "internal"}
            onChange={(e) => setForm((f) => ({ ...f, default_data_class: e.target.value as DataClass }))}
            disabled={!isAdmin}
          >
            {DATA_CLASSES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="stack-form" style={{ border: "none", padding: 0 }}>
          <legend style={{ fontWeight: 500, fontSize: "0.9rem" }}>Classes for what is found in the text</legend>
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            Built in: {BUILT_IN_CLASSES.map((b) => `${b.entity} is ${dataClassLabel(b.cls)}`).join("; ")}. Your entries override these. A name only has an effect
            if the gateway can detect it: ssn, payment_card and email out of the box, or Presidio's entity types if Presidio is installed.
          </p>
          {Object.keys(map).length > 0 ? (
            <ul className="stack-form" style={{ listStyle: "none", margin: 0, padding: 0 }} aria-label="Classes for detected data">
              {Object.entries(map).map(([name, cls]) => (
                <li key={name} className="flex items-center gap-2">
                  <code>{name}</code>
                  <span>is {dataClassLabel(cls)}</span>
                  {isAdmin ? (
                    <button type="button" className="btn-icon-only" onClick={() => removeMapping(name)} aria-label={`Remove ${name}`}>
                      <X size={14} className="text-accent-rose" aria-hidden />
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {isAdmin ? (
            <div className="flex items-end gap-2 flex-wrap">
              <label className="inline-control" htmlFor={ids.entity}>
                Detected kind
                <input id={ids.entity} type="text" value={entity} onChange={(e) => setEntity(e.target.value)} onKeyDown={onEnter} placeholder="ssn" autoComplete="off" />
              </label>
              <label className="inline-control" htmlFor={ids.entityClass}>
                Class
                <select id={ids.entityClass} value={entityClass} onChange={(e) => setEntityClass(e.target.value as DataClass)}>
                  {DATA_CLASSES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={addMapping} className="flex items-center gap-1.5" aria-label="Add class for detected kind">
                <Plus size={14} aria-hidden />
                Add
              </button>
            </div>
          ) : null}
        </fieldset>
      </section>

      <section className="surface-panel stack-form">
        <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Routing</h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          Decide which model may serve a request from its data class, using the model registry. Turn it on in two steps: Preview, then Enforce.
        </p>
        <div className="flex flex-col gap-2" role="radiogroup" aria-label="Routing mode">
          {MODES.map((mode) => (
            <label key={mode.value} className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="radio"
                name="routing_mode"
                value={mode.value}
                checked={(form.routing_mode ?? "off") === mode.value}
                onChange={() => setForm((f) => ({ ...f, routing_mode: mode.value }))}
                disabled={!isAdmin}
                style={{ marginTop: 3 }}
              />
              <div>
                <span className="font-medium" style={{ fontSize: "0.9rem" }}>
                  {mode.title}
                </span>
                <p className="muted" style={{ fontSize: "0.82rem" }}>
                  {mode.detail}
                </p>
              </div>
            </label>
          ))}
        </div>
        <label className="inline-control" htmlFor={ids.risk}>
          Highest risk rating a model may have
          <select
            id={ids.risk}
            value={form.max_risk_rating ?? "high"}
            onChange={(e) => setForm((f) => ({ ...f, max_risk_rating: e.target.value as Rating }))}
            disabled={!isAdmin}
          >
            {RISKS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-start gap-2.5">
          <input
            id={ids.quality}
            type="checkbox"
            checked={(form.routing_quality_signal ?? "off") === "feedback"}
            onChange={(e) => setForm((f) => ({ ...f, routing_quality_signal: e.target.checked ? "feedback" : "off" }))}
            disabled={!isAdmin}
            aria-describedby={ids.qualityHelp}
            style={{ marginTop: 3 }}
          />
          <div>
            <label htmlFor={ids.quality} className="font-medium" style={{ fontSize: "0.9rem" }}>
              Prefer better-rated models for capability requests
            </label>
            <p id={ids.qualityHelp} className="muted" style={{ fontSize: "0.82rem" }}>
              For <code>cap:NAME</code> requests, pick the authorized model with the best thumbs feedback from the last 30 days when the gap is clear (at least 20 ratings; models within 5 points of the best are tied and cost decides). It only chooses among models already authorized for the request. Off: the cheapest authorized model.
            </p>
          </div>
        </div>
      </section>

      <section className="surface-panel stack-form">
        <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>State kept at the provider</h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          The Responses API can keep a conversation at the provider (<code>store</code>, <code>previous_response_id</code>, uploaded files). That data then sits where your retention, residency and routing rules do not reach. It is <strong>off by default</strong>: the gateway always sends <code>store=false</code> and refuses requests that rely on provider state.
        </p>
        <label className="flex items-center gap-2 text-sm" htmlFor={ids.state}>
          <input
            id={ids.state}
            type="checkbox"
            checked={form.allow_provider_response_state ?? false}
            disabled={!isAdmin}
            onChange={(e) => setForm((f) => ({ ...f, allow_provider_response_state: e.target.checked }))}
          />
          Allow requests to keep state at the provider
        </label>
      </section>

      {isAdmin ? <RoutingPreview token={token} unsaved={unsaved} /> : null}
    </>
  );
}
