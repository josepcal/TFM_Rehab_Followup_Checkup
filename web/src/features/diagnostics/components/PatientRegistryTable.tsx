import { useMemo, useState } from "react";

import type { PatientOut } from "../../../api/patients";

type PatientRegistryTableProps = {
  patients: PatientOut[];
  selectedPatientId?: string;
  selectedPatientDiagnosticCount?: number;
  isLoading: boolean;
  error?: unknown;
  onOpenPatient: (patientId: string) => void;
};

export function PatientRegistryTable({
  patients,
  selectedPatientId,
  selectedPatientDiagnosticCount,
  isLoading,
  error,
  onOpenPatient,
}: PatientRegistryTableProps) {
  const [query, setQuery] = useState("");
  const rows = useMemo(() => {
    const normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) {
      return patients;
    }

    return patients.filter((patient) =>
      normalizeSearchText(`${patient.nombre} ${patient.apellidos} ${patient.id}`).includes(
        normalizedQuery,
      ),
    );
  }, [patients, query]);

  if (isLoading) {
    return (
      <p className="state-card" role="status">
        Loading patients…
      </p>
    );
  }

  if (error) {
    return (
      <p className="state-card" role="alert">
        Unable to load patients.
      </p>
    );
  }

  return (
    <section className="patient-registry-screen" aria-label="Patient registry">
      <div className="registry-heading">
        <div>
          <h3>Patients</h3>
          <p>Search the registry and open a record to begin a diagnostic assessment.</p>
        </div>
        <div className="registry-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="Search by name or patient ID"
            placeholder="Search by name or patient ID..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <div className="patient-table-card">
        <table className="patient-table">
          <thead>
            <tr>
              <th scope="col">Patient</th>
              <th scope="col">Patient ID</th>
              <th scope="col">Diagnostics</th>
              <th scope="col" aria-label="Open record" />
            </tr>
          </thead>
          <tbody>
            {rows.map((patient) => {
              const isSelected = patient.id === selectedPatientId;
              const diagnosticLabel = isSelected
                ? String(selectedPatientDiagnosticCount ?? 0)
                : "Open record";

              return (
                <tr key={patient.id}>
                  <td>
                    <button
                      type="button"
                      className="patient-row-button"
                      onClick={() => onOpenPatient(patient.id)}
                    >
                      <span className="patient-avatar patient-avatar-small" aria-hidden="true">
                        {getInitials(patient)}
                      </span>
                      <span>
                        <strong>
                          {patient.nombre} {patient.apellidos}
                        </strong>
                        <small>Clinical record</small>
                      </span>
                    </button>
                  </td>
                  <td className="muted-cell">{patient.id}</td>
                  <td>
                    <span className="status-badge">{diagnosticLabel}</span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="chevron-button"
                      aria-label={`Open ${patient.nombre} ${patient.apellidos}`}
                      onClick={() => onOpenPatient(patient.id)}
                    >
                      ›
                    </button>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="table-empty-state">
                  No patients match “{query}”.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function getInitials(patient: PatientOut) {
  return [patient.nombre, patient.apellidos]
    .filter(Boolean)
    .map((part) => part.trim().charAt(0).toUpperCase())
    .join("")
    .slice(0, 2);
}

export function normalizeSearchText(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}
