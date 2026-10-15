import { useEffect, useRef, useState } from "react";

import { commitBankImport, previewBankImport } from "../api/client";
import type { BankImportPreview, BankImportResult, TransactionsSnapshot } from "../api/contracts";

interface BankImportPageProps {
  importRequestKey: number;
  onImportCompleted: () => void;
  onNavigateSettings: () => void;
  onViewChange: (view: "journal" | "import" | "history") => void;
  snapshot: TransactionsSnapshot;
  token: string;
  view: "import" | "history";
}

interface SelectedFile {
  name: string;
  contentBase64: string;
}

const money = new Intl.NumberFormat("fr-FR", {
  currency: "EUR",
  currencyDisplay: "code",
  minimumFractionDigits: 2,
  style: "currency",
});

const date = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function BankImportPage({
  importRequestKey,
  onImportCompleted,
  onNavigateSettings,
  onViewChange,
  snapshot,
  token,
  view,
}: BankImportPageProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const lastRequestKey = useRef(0);
  const activeAccounts = snapshot.accounts.filter((account) => account.status === "Actif");
  const [accountId, setAccountId] = useState(String(activeAccounts[0]?.id ?? snapshot.accounts[0]?.id ?? ""));
  const [file, setFile] = useState<SelectedFile>();
  const [preview, setPreview] = useState<BankImportPreview>();
  const [result, setResult] = useState<BankImportResult>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (importRequestKey > 0 && importRequestKey !== lastRequestKey.current && view === "import") {
      lastRequestKey.current = importRequestKey;
      inputRef.current?.click();
    }
  }, [importRequestKey, view]);

  useEffect(() => {
    if (!accountId && activeAccounts[0]) setAccountId(String(activeAccounts[0].id));
  }, [accountId, activeAccounts]);

  async function analyze(selectedFile: SelectedFile, selectedAccountId: string) {
    setBusy(true);
    setError(undefined);
    setResult(undefined);
    try {
      const data = await previewBankImport(token, {
        accountId: selectedAccountId ? Number(selectedAccountId) : null,
        contentBase64: selectedFile.contentBase64,
        fileName: selectedFile.name,
      });
      setPreview(data);
      if (data.accountId) setAccountId(String(data.accountId));
    } catch (cause: unknown) {
      setPreview(undefined);
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function selectFile(selected: File | undefined) {
    if (!selected) return;
    setError(undefined);
    if (selected.size > 10 * 1024 * 1024) {
      setError("Le relevé dépasse la taille maximale de 10 Mo.");
      return;
    }
    try {
      const selectedFile = {
        name: selected.name,
        contentBase64: await readFileAsBase64(selected),
      };
      setFile(selectedFile);
      await analyze(selectedFile, accountId);
    } catch (cause: unknown) {
      setError(errorMessage(cause));
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function changeAccount(nextAccountId: string) {
    setAccountId(nextAccountId);
    if (file) await analyze(file, nextAccountId);
  }

  async function validateImport() {
    if (!preview || !preview.accountConsistent || preview.newCount === 0) return;
    const confirmed = window.confirm(
      "Importer " + preview.newCount + " opération(s) dans le compte sélectionné ?\n\n"
      + preview.duplicateCount + " doublon(s) seront ignorés automatiquement.",
    );
    if (!confirmed) return;
    setBusy(true);
    setError(undefined);
    try {
      const imported = await commitBankImport(
        token,
        preview.previewId,
        accountId ? Number(accountId) : null,
      );
      setResult(imported);
      setPreview(undefined);
      setFile(undefined);
      onImportCompleted();
    } catch (cause: unknown) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFile(undefined);
    setPreview(undefined);
    setResult(undefined);
    setError(undefined);
  }

  return (
    <div className="bank-import-page">
      <input
        accept=".csv,.xlsx,.qif,.ofx"
        aria-label="Choisir un relevé bancaire"
        className="visually-hidden"
        onChange={(event) => void selectFile(event.target.files?.[0])}
        ref={inputRef}
        type="file"
      />
      <nav aria-label="Sous-navigation des transactions" className="transactions-subnav">
        <button onClick={() => onViewChange("journal")} type="button">Transactions</button>
        <button className={view === "import" ? "active" : ""} onClick={() => onViewChange("import")} type="button">Imports</button>
        <button onClick={onNavigateSettings} type="button">Règles auto</button>
        <button className={view === "history" ? "active" : ""} onClick={() => onViewChange("history")} type="button">Lots</button>
      </nav>

      {view === "history" ? (
        <ImportHistory snapshot={snapshot} onChoose={() => onViewChange("import")} />
      ) : (
        <div className="bank-import-grid" aria-busy={busy}>
          <article className="card bank-import-assistant">
            <div className="bank-import-heading">
              <div><h2>Assistant d’import</h2><p>Une intégration automatique locale, sans connexion bancaire permanente.</p></div>
              <button className="secondary-button" disabled={busy} onClick={() => inputRef.current?.click()} type="button">
                {file ? "Changer de fichier" : "Choisir un fichier"}
              </button>
            </div>

            <ol className="import-steps">
              <li className={file ? "complete" : "active"}><span>1</span><strong>Fichier reconnu</strong></li>
              <li className={preview ? "active" : ""}><span>2</span><strong>Aperçu contrôlé</strong></li>
              <li className={result ? "complete" : ""}><span>3</span><strong>Validation</strong></li>
            </ol>

            {busy && <div className="import-loading"><span aria-hidden="true" />Analyse locale du relevé…</div>}
            {error && <div className="import-message import-message--error"><strong>Import impossible</strong><p>{error}</p></div>}
            {result && <ImportSuccess result={result} onReset={reset} />}

            {!busy && !result && !preview && !error && (
              <button className="import-dropzone" onClick={() => inputRef.current?.click()} type="button">
                <span aria-hidden="true">⇧</span>
                <strong>Choisissez votre relevé bancaire</strong>
                <small>CSV, XLSX, QIF ou OFX · 10 Mo maximum</small>
                <em>Le fichier reste sur cet ordinateur.</em>
              </button>
            )}

            {preview && (
              <>
                <div className="import-file-card">
                  <div>
                    <strong>Fichier : {preview.fileName}</strong>
                    <span>{preview.profile} · format {preview.format}</span>
                  </div>
                  <label>
                    <span>Compte cible</span>
                    <select onChange={(event) => void changeAccount(event.target.value)} value={accountId}>
                      <option value="">Sélectionner un compte</option>
                      {activeAccounts.map((account) => (
                        <option key={account.id} value={account.id}>{account.bank ? account.bank + " — " : ""}{account.name}</option>
                      ))}
                    </select>
                  </label>
                  <span className={preview.accountConsistent ? "status-chip status-chip--success" : "status-chip status-chip--warning"}>
                    {preview.accountConsistent ? "Compte cohérent" : "Compte à vérifier"}
                  </span>
                  <small>{preview.accountMessage}</small>
                </div>
                <div className="import-preview-wrap">
                  <table className="import-preview-table">
                    <thead><tr><th>Date</th><th>Libellé enrichi</th><th>Catégorie</th><th>Statut</th><th>Montant</th></tr></thead>
                    <tbody>
                      {preview.rows.map((row, index) => (
                        <tr className={row.duplicate ? "duplicate" : ""} key={row.date + row.label + index}>
                          <td>{formatDate(row.date)}</td>
                          <td title={row.label}>{row.label}</td>
                          <td><span className="transaction-pill transaction-pill--muted">{row.category}</span></td>
                          <td><span className={row.duplicate ? "import-row-status import-row-status--duplicate" : "import-row-status"}>{row.status}</span></td>
                          <td className={row.amount < 0 ? "transaction-amount transaction-amount--negative" : "transaction-amount transaction-amount--positive"}>{signedMoney(row.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {preview.rowsTruncated && <small className="import-limit-note">Aperçu limité aux 200 premières lignes ; toutes les lignes reconnues seront traitées.</small>}
              </>
            )}
          </article>

          <aside className="card import-control">
            <div><h2>Volet de contrôle</h2><p>Avant intégration définitive.</p></div>
            <ControlMetric label="Opérations reconnues" tone="success" value={preview?.recognizedCount ?? 0} />
            <ControlMetric label="Doublons ignorés" tone="warning" value={preview?.duplicateCount ?? 0} />
            <ControlMetric label="Lignes rejetées" tone={preview?.errorCount ? "warning" : "success"} value={preview?.errorCount ?? 0} />
            <ControlMetric label="Format dates/montants" tone={preview ? "blue" : "muted"} value={preview ? "OK" : "—"} />
            <div className="import-control-actions">
              <button className="secondary-button" disabled={busy} onClick={reset} type="button">Annuler</button>
              <button
                disabled={busy || !preview?.accountConsistent || preview.newCount === 0}
                onClick={() => void validateImport()}
                type="button"
              >
                {busy ? "Traitement…" : "Valider l’import"}
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function ControlMetric({ label, tone, value }: { label: string; tone: "blue" | "muted" | "success" | "warning"; value: number | string }) {
  const badges = { blue: "Validé", muted: "En attente", success: "OK", warning: "À contrôler" };
  return (
    <div className="import-control-metric">
      <div><span>{label}</span><strong>{value}</strong></div>
      <em className={"import-control-badge import-control-badge--" + tone}>{badges[tone]}</em>
    </div>
  );
}

function ImportSuccess({ onReset, result }: { onReset: () => void; result: BankImportResult }) {
  return (
    <div className="import-success">
      <span aria-hidden="true">✓</span>
      <div>
        <h3>Import terminé</h3>
        <p>{result.importedCount} opération(s) ajoutée(s), {result.duplicateCount} doublon(s) ignoré(s).</p>
        <ul>
          <li>{result.categorization.automatic} catégorisation(s) automatique(s)</li>
          <li>{result.reconciliation.automatic} rapprochement(s) automatique(s)</li>
          <li>{result.reconciliation.toReview} rapprochement(s) à vérifier</li>
        </ul>
        <button className="secondary-button" onClick={onReset} type="button">Importer un autre relevé</button>
      </div>
    </div>
  );
}

function ImportHistory({ onChoose, snapshot }: { onChoose: () => void; snapshot: TransactionsSnapshot }) {
  const item = snapshot.recentImport;
  return (
    <article className="card import-history">
      <div className="bank-import-heading">
        <div><h2>Lots d’import</h2><p>Dernier lot enregistré par le moteur Python.</p></div>
        <button onClick={onChoose} type="button">Nouvel import</button>
      </div>
      {item ? (
        <div className="import-history-card">
          <div><strong>{item.fileName}</strong><span>{item.accountName} · {formatDateTime(item.createdAt)}</span></div>
          <dl>
            <div><dt>Importées</dt><dd>{item.importedCount}</dd></div>
            <div><dt>Doublons</dt><dd>{item.duplicateCount}</dd></div>
            <div><dt>Erreurs</dt><dd>{item.errorCount}</dd></div>
            <div><dt>Statut</dt><dd>{item.status}</dd></div>
          </dl>
        </div>
      ) : <div className="import-history-empty">Aucun lot d’import enregistré.</div>}
    </article>
  );
}

async function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Le relevé ne peut pas être lu."));
    reader.onload = () => {
      const content = typeof reader.result === "string" ? reader.result : "";
      const separator = content.indexOf(",");
      if (separator < 0) reject(new Error("Le relevé ne peut pas être encodé."));
      else resolve(content.slice(separator + 1));
    };
    reader.readAsDataURL(file);
  });
}

function signedMoney(value: number): string {
  if (value === 0) return money.format(value);
  return (value > 0 ? "+ " : "- ") + money.format(Math.abs(value));
}

function formatDate(value: string): string {
  if (!value) return "—";
  const parsed = new Date(value + "T12:00:00");
  return Number.isNaN(parsed.getTime()) ? value : date.format(parsed);
}

function formatDateTime(value: string): string {
  if (!value) return "—";
  const parsed = new Date(value.includes("T") ? value : value.replace(" ", "T") + "Z");
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Le moteur d’import ne répond pas.";
}
