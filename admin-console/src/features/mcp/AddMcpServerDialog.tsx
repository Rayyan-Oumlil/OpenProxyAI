import { useState } from "react";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import type { CreateMcpServerRequest, PinMode, ScanMode } from "./types";

const NAME_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

interface Props {
  open: boolean;
  onClose: () => void;
  onSave: (data: CreateMcpServerRequest) => void;
  isSaving: boolean;
}

export function AddMcpServerDialog({ open, onClose, onSave, isSaving }: Props) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [authHeader, setAuthHeader] = useState("");
  const [pinMode, setPinMode] = useState<PinMode>("warn");
  const [scanMode, setScanMode] = useState<ScanMode>("log");
  const nameError = name !== "" && !NAME_PATTERN.test(name);
  const urlError = url !== "" && !/^https:\/\//i.test(url);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (nameError || urlError) return;
    onSave({
      name,
      url,
      ...(authHeader.trim() ? { auth_header: authHeader.trim() } : {}),
      pin_mode: pinMode,
      scan_mode: scanMode,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add MCP server</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="stack-form">
          <label className="inline-control">
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="github"
              required
              maxLength={40}
              aria-invalid={nameError}
              aria-describedby="mcp-name-help"
            />
          </label>
          <p id="mcp-name-help" className={nameError ? "mcp-field-error" : "text-muted-sm"}>
            Lowercase letters, digits and single hyphens. Tools appear as name__tool.
          </p>
          <label className="inline-control">
            URL
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://mcp.example.com/mcp"
              required
              aria-invalid={urlError}
              aria-describedby="mcp-url-help"
            />
          </label>
          <p id="mcp-url-help" className={urlError ? "mcp-field-error" : "text-muted-sm"}>
            HTTPS only, public address.
          </p>
          <label className="inline-control">
            Authorization header (optional)
            <input
              type="password"
              value={authHeader}
              onChange={(e) => setAuthHeader(e.target.value)}
              placeholder="Bearer ..."
              autoComplete="new-password"
            />
          </label>
          <label className="inline-control">
            Tool pinning
            <select value={pinMode} onChange={(e) => setPinMode(e.target.value as PinMode)}>
              <option value="warn">Warn: trust first sight, flag changes</option>
              <option value="enforce">Enforce: admin approval required</option>
              <option value="off">Off</option>
            </select>
          </label>
          <label className="inline-control">
            Injection scan
            <select value={scanMode} onChange={(e) => setScanMode(e.target.value as ScanMode)}>
              <option value="log">Log findings</option>
              <option value="redact">Redact findings</option>
              <option value="block">Block flagged results</option>
              <option value="off">Off</option>
            </select>
          </label>
          <DialogFooter>
            <button type="button" onClick={onClose} className="btn-outline">
              Cancel
            </button>
            <button type="submit" disabled={isSaving || nameError || urlError} className="bg-accent-sky">
              {isSaving ? "Adding…" : "Add server"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
