import { useState } from "react";

import type { ConsentApi } from "../../api/consent";

const CONSENT_TEXT =
  "Para continuar con la grabación, necesito tu consentimiento. Tu voz es un dato biométrico de categoría especial según el RGPD (art. 9). La grabación se utilizará exclusivamente para el seguimiento de tu programa de rehabilitación. Puedes retirar tu consentimiento en cualquier momento.";

export type ConsentModalProps = {
  programId: string;
  api: ConsentApi;
  onGranted: () => void;
  onCancel: () => void;
};

export function ConsentModal({ programId, api, onGranted, onCancel }: ConsentModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  async function handleAccept() {
    setLoading(true);
    setError(undefined);
    try {
      await api.grantConsent(programId, CONSENT_TEXT);
      onGranted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save consent. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 10,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.5)",
      }}
    >
      <section
        style={{
          background: "#fff",
          borderRadius: "8px",
          padding: "2rem",
          maxWidth: "480px",
          width: "100%",
          boxShadow: "0 4px 24px rgba(0,0,0,0.18)",
        }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-modal-title"
      >
        <h3 id="consent-modal-title" style={{ marginTop: 0 }}>Consentimiento RGPD</h3>
        <p style={{ marginBottom: "1.5rem", lineHeight: 1.6 }}>{CONSENT_TEXT}</p>

        {error ? (
          <p role="alert" style={{ color: "#dc2626", marginBottom: "1rem" }}>{error}</p>
        ) : null}

        {loading ? (
          <p role="status" style={{ marginBottom: "1rem", color: "#6b7280" }}>Guardando consentimiento…</p>
        ) : null}

        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
          <button
            type="button"
            disabled={loading}
            onClick={onCancel}
            style={{ padding: "0.5rem 1.25rem", cursor: loading ? "not-allowed" : "pointer" }}
          >
            Cancelar
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={handleAccept}
            style={{
              padding: "0.5rem 1.25rem",
              background: "#7c3aed",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            Acepto y grabo
          </button>
        </div>
      </section>
    </div>
  );
}
