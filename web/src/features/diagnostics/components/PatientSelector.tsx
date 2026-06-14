import type { PatientOut } from "../../../api/patients";

type PatientSelectorProps = {
  patients: PatientOut[];
  selectedPatientId?: string;
  isLoading: boolean;
  error?: unknown;
  onSelectPatient: (patientId: string) => void;
};

export function PatientSelector({
  patients,
  selectedPatientId,
  isLoading,
  error,
  onSelectPatient,
}: PatientSelectorProps) {
  if (isLoading) {
    return <p role="status">Loading patients…</p>;
  }

  if (error) {
    return <p role="alert">Unable to load patients.</p>;
  }

  if (patients.length === 0) {
    return <p>No assigned patients found.</p>;
  }

  return (
    <label className="field">
      <span>Select patient</span>
      <select
        value={selectedPatientId ?? ""}
        onChange={(event) => onSelectPatient(event.target.value)}
      >
        <option value="" disabled>
          Choose a patient
        </option>
        {patients.map((patient) => (
          <option key={patient.id} value={patient.id}>
            {patient.nombre} {patient.apellidos}
          </option>
        ))}
      </select>
    </label>
  );
}
