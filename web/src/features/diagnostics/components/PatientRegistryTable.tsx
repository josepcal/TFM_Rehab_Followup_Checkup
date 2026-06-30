import { useMemo, useState } from "react";

import type { PatientOut } from "../../../api/patients";

type PatientRegistryTableProps = {
  patients: PatientOut[];
  selectedPatientId?: string;
  selectedPatientDiagnosticCount?: number;
  totalPatients: number;
  totalDiagnostics: number;
  isLoading: boolean;
  error?: unknown;
  onOpenPatient: (patientId: string) => void;
};

export function PatientRegistryTable({
  patients,
  selectedPatientId,
  selectedPatientDiagnosticCount,
  totalPatients,
  totalDiagnostics,
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
      normalizeSearchText(
        `${patient.nombre} ${patient.apellidos} ${patient.id} ${patient.sex ?? ""} ${
          patient.birth_date ? calculateAge(patient.birth_date) : ""
        } ${patient.last_assessment ? formatDate(patient.last_assessment) : ""}`,
      ).includes(normalizedQuery),
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
        <div className="registry-stat-strip" aria-label="Registry summary">
          <div className="stat-card">
            <span className="stat-icon stat-icon-patients" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
            <span>
              <span className="stat-value">{totalPatients}</span>
              <span className="stat-label">Patients</span>
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-icon stat-icon-diagnostics" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
                <path d="M14 2v4a2 2 0 0 0 2 2h4" />
                <path d="M10 9H8" />
                <path d="M16 13H8" />
                <path d="M16 17H8" />
              </svg>
            </span>
            <span>
              <span className="stat-value">{totalDiagnostics}</span>
              <span className="stat-label">Diagnostics</span>
            </span>
          </div>
        </div>
        <div className="registry-search">
          <span aria-hidden="true" className="registry-search-icon">
            <svg viewBox="0 0 24 24" focusable="false">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
          </span>
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
              <th scope="col" className="responsive-table-cell">Age</th>
              <th scope="col" className="responsive-table-cell">Sex</th>
              <th scope="col">Diagnostics</th>
              <th scope="col" className="wide-table-cell">Last assessment</th>
              <th scope="col" aria-label="Open record" />
            </tr>
          </thead>
          <tbody>
            {rows.map((patient) => {
              const isSelected = patient.id === selectedPatientId;
              const diagnosticLabel = isSelected
                ? String(selectedPatientDiagnosticCount ?? 0)
                : "—";

              return (
                <tr key={patient.id}>
                  <td>
                    <button
                      type="button"
                      className="patient-row-button"
                      aria-label={`Open ${patient.nombre} ${patient.apellidos} clinical record`}
                      onClick={() => onOpenPatient(patient.id)}
                    >
                      <span className="patient-avatar-small" aria-hidden="true">
                        {getInitials(patient)}
                      </span>
                      <span>
                        <strong>
                          {patient.nombre} {patient.apellidos}
                        </strong>
                        {patient.birth_date ? (
                          <small>{calculateAge(patient.birth_date)} years</small>
                        ) : null}
                      </span>
                    </button>
                  </td>
                  <td className="muted-cell responsive-table-cell">
                    {patient.birth_date ? calculateAge(patient.birth_date) : "—"}
                  </td>
                  <td className="muted-cell responsive-table-cell">{formatSex(patient.sex)}</td>
                  <td>
                    <span className="status-badge">{diagnosticLabel}</span>
                  </td>
                  <td className="muted-cell wide-table-cell">
                    {patient.last_assessment ? formatDate(patient.last_assessment) : "—"}
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
                <td colSpan={6} className="table-empty-state">
                  {query
                    ? `No patients match "${query}".`
                    : "No patients registered yet."}
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

function calculateAge(birthDate: string) {
  const dob = new Date(birthDate);
  if (Number.isNaN(dob.getTime())) {
    return "—";
  }

  const now = new Date();
  let age = now.getFullYear() - dob.getFullYear();
  const monthDiff = now.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < dob.getDate())) {
    age -= 1;
  }

  return String(age);
}

function formatSex(sex: PatientOut["sex"]) {
  const labels: Record<string, string> = {
    female: "Female",
    male: "Male",
    other: "Other",
    unspecified: "Unspecified",
  };

  return sex ? (labels[sex] ?? sex) : "—";
}

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}
