"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, downloadFile } from "../lib/api";

type Column = {
  name: string;
  data_type: "string" | "integer" | "number" | "boolean";
  description: string;
  required: boolean;
  allowed_values: string[];
};
type Spec = { dataset_type: string; languages: string[]; columns: Column[]; constraints: string[] };
type Dataset = { id: string; name: string; status: string; created_at: string };
type Version = {
  id: string;
  version_number: number;
  record_count: number;
  quality_report: { quality_score?: number };
};

const initialPrompt =
  "Generate 100 customer support conversations for an Indian banking app. Include customer queries, agent responses, intent, sentiment, and resolution status in English and Hindi.";

type Format = "csv" | "json" | "jsonl" | "xlsx";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("demo@dataforge.local");
  const [password, setPassword] = useState("ChangeMe12345!");
  const [prompt, setPrompt] = useState(initialPrompt);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [count, setCount] = useState(100);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [message, setMessage] = useState("Create an account or sign in to begin.");
  const [busy, setBusy] = useState(false);

  const [inspected, setInspected] = useState<Dataset | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("dataforge_access_token");
    if (stored) {
      setToken(stored);
      void loadDatasets(stored);
    }
  }, []);

  async function authenticate(event: FormEvent, mode: "login" | "register") {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api<{ access_token: string }>(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem("dataforge_access_token", result.access_token);
      setToken(result.access_token);
      await loadDatasets(result.access_token);
      setMessage(`Signed in as ${email}.`);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    localStorage.removeItem("dataforge_access_token");
    setToken(null);
    setDatasets([]);
    setInspected(null);
    setVersions([]);
    setSpec(null);
    setMessage("Signed out.");
  }

  async function loadDatasets(activeToken = token) {
    if (!activeToken) return;
    try {
      setDatasets(await api<Dataset[]>("/datasets", {}, activeToken));
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  async function analyze() {
    if (!token) return setMessage("Sign in before analyzing a prompt.");
    setBusy(true);
    try {
      const result = await api<{ specification: Spec; suggested_record_count: number }>(
        "/prompts/analyze",
        { method: "POST", body: JSON.stringify({ prompt, record_count: count }) },
        token
      );
      setSpec(result.specification);
      setCount(result.suggested_record_count);
      setMessage("Schema proposed. Review it, then generate your dataset.");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createAndGenerate() {
    if (!token || !spec) return setMessage("Sign in and analyze a prompt first.");
    setBusy(true);
    try {
      const dataset = await api<Dataset>(
        "/datasets",
        {
          method: "POST",
          body: JSON.stringify({
            name: `${spec.dataset_type.replaceAll("_", " ")} dataset`,
            description: prompt,
            specification: spec,
          }),
        },
        token
      );
      const job = await api<{ status: string; generated_records: number }>(
        `/datasets/${dataset.id}/generate`,
        { method: "POST", body: JSON.stringify({ record_count: count }) },
        token
      );
      setMessage(`Generation ${job.status}: ${job.generated_records} records created.`);
      await loadDatasets();
      await inspect(dataset);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function inspect(dataset: Dataset) {
    if (!token) return;
    setInspected(dataset);
    setVersions([]);
    setVersionsLoading(true);
    try {
      const v = await api<Version[]>(`/datasets/${dataset.id}/versions`, {}, token);
      setVersions(v);
      if (v.length === 0) {
        setMessage("No versions yet — generate this dataset first.");
      } else {
        setMessage(`${v.length} version(s) available. Choose a format below to download.`);
      }
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setVersionsLoading(false);
    }
  }

  async function handleDownload(version: Version, format: Format) {
    if (!token) return;
    setBusy(true);
    try {
      const filename = `dataforge-v${version.version_number}.${format}`;
      await downloadFile(
        `/dataset-versions/${version.id}/export?format=${format}`,
        token,
        filename
      );
      setMessage(`Downloaded ${filename} (${version.record_count} records).`);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header>
        <div>
          <span className="mark">DF</span>
          <b>DataForge AI</b>
        </div>
        <p>
          {token ? (
            <>
              Prompt-to-dataset generation platform{" "}
              <button className="secondary" style={{ marginLeft: 12 }} onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            "Prompt-to-dataset generation platform"
          )}
        </p>
      </header>

      <p className="notice" role="status">
        {message}
      </p>

      {!token && (
        <section className="auth">
          <h1>Build trustworthy synthetic datasets</h1>
          <p>
            Start with a natural-language request, review the schema, and generate
            versioned data with quality checks.
          </p>
          <form onSubmit={(e) => authenticate(e, "login")}>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              aria-label="Email"
              placeholder="Email"
            />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              aria-label="Password"
              placeholder="Password (min 12 chars)"
            />
            <div>
              <button type="submit" disabled={busy}>
                {busy ? "Working…" : "Sign in"}
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={(e) => authenticate(e, "register")}
              >
                Create account
              </button>
            </div>
          </form>
        </section>
      )}

      {token && (
        <div className="workspace">
          <section className="studio">
            <p className="eyebrow">PROMPT STUDIO</p>
            <h1>Describe the dataset you need</h1>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={8}
            />
            <label>
              Records{" "}
              <input
                type="number"
                min="1"
                max="100000"
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
              />
            </label>
            <button onClick={analyze} disabled={busy}>
              {busy ? "Working…" : "Analyze prompt"}
            </button>
          </section>

          <section className="schema">
            <p className="eyebrow">GENERATION PLAN</p>
            <h2>{spec ? spec.dataset_type.replaceAll("_", " ") : "Awaiting analysis"}</h2>
            {spec ? (
              <>
                <p>Languages: {spec.languages.join(", ")}</p>
                <ul>
                  {spec.columns.map((column) => (
                    <li key={column.name}>
                      <code>{column.name}</code>
                      <span>
                        {column.data_type} · {column.description}
                      </span>
                    </li>
                  ))}
                </ul>
                <button onClick={createAndGenerate} disabled={busy}>
                  {busy ? "Generating…" : `Generate ${count.toLocaleString()} records`}
                </button>
              </>
            ) : (
              <p>Analyze a prompt to produce an editable, typed specification.</p>
            )}
          </section>
        </div>
      )}

      {token && (
        <section className="datasets">
          <div>
            <p className="eyebrow">DATASETS</p>
            <h2>Your generation history</h2>
          </div>
          {datasets.length ? (
            <ul>
              {datasets.map((dataset) => (
                <li key={dataset.id}>
                  <div>
                    <b>{dataset.name}</b>
                    <span>
                      {dataset.status} · {new Date(dataset.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <button
                    className="secondary"
                    onClick={() => inspect(dataset)}
                    disabled={busy}
                  >
                    Inspect
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>No datasets yet.</p>
          )}

          {inspected && (
            <div
              style={{
                marginTop: 24,
                padding: 20,
                border: "1px solid var(--line)",
                borderRadius: 12,
                background: "var(--mist)",
              }}
            >
              <h3 style={{ margin: "0 0 12px" }}>{inspected.name}</h3>
              {versionsLoading && <p>Loading versions…</p>}
              {!versionsLoading && versions.length === 0 && <p>No versions yet.</p>}
              {!versionsLoading && versions.length > 0 && (
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                  {versions.map((version) => (
                    <li
                      key={version.id}
                      style={{
                        display: "grid",
                        gap: 8,
                        padding: "12px 0",
                        borderBottom: "1px solid var(--line)",
                      }}
                    >
                      <div>
                        <b>Version {version.version_number}</b>{" "}
                        <span style={{ color: "var(--muted)" }}>
                          · {version.record_count} records · quality{" "}
                          {version.quality_report?.quality_score ?? "pending"}/100
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {(["csv", "json", "jsonl", "xlsx"] as Format[]).map((fmt) => (
                          <button
                            key={fmt}
                            className="secondary"
                            disabled={busy}
                            onClick={() => handleDownload(version, fmt)}
                          >
                            {busy ? "…" : `Download ${fmt.toUpperCase()}`}
                          </button>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  );
}