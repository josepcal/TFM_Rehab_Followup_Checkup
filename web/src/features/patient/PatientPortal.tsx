import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { DoctorOut, DoctorsApi } from "../../api/doctors";
import type { PatientPortalApi } from "../../api/patientPortal";
import type { ProgramExerciseOut, ProgramOut } from "../../api/programs";
import type { ExerciseRecordingListItem, RecordingsApi } from "../../api/recordings";

type PatientPortalFeatureApi = PatientPortalApi & RecordingsApi & Pick<DoctorsApi, "listDoctors">;

export function PatientPortal({ api }: { api: PatientPortalFeatureApi }) {
  const [selectedProgramId, setSelectedProgramId] = useState<string>();
  const [exerciseProgramId, setExerciseProgramId] = useState<string>();
  const [recordingExercise, setRecordingExercise] = useState<ProgramExerciseOut>();
  const patientQuery = useQuery({ queryKey: ["patient-portal", "me"], queryFn: () => api.getMyPatient() });
  const diagnosticsQuery = useQuery({ queryKey: ["patient-portal", "diagnostics"], queryFn: () => api.listMyDiagnostics() });
  const programsQuery = useQuery({ queryKey: ["patient-portal", "programs"], queryFn: () => api.listMyPrograms() });
  const doctorsQuery = useQuery({ queryKey: ["patient-portal", "doctors"], queryFn: () => api.listDoctors() });
  const programDetailQuery = useQuery({
    queryKey: ["patient-portal", "program", selectedProgramId],
    queryFn: () => api.getMyProgram(selectedProgramId ?? ""),
    enabled: Boolean(selectedProgramId),
  });
  const exerciseProgramDetailQuery = useQuery({
    queryKey: ["patient-portal", "program", exerciseProgramId],
    queryFn: () => api.getMyProgram(exerciseProgramId ?? ""),
    enabled: Boolean(exerciseProgramId),
  });
  const programExercisesQuery = useQuery({
    queryKey: ["patient-portal", "program-exercises", selectedProgramId],
    queryFn: () => api.listMyProgramExercises(selectedProgramId ?? ""),
    enabled: Boolean(selectedProgramId),
  });
  const recordingExercisesQuery = useQuery({
    queryKey: ["patient-portal", "recording-exercises", exerciseProgramId],
    queryFn: () => api.listMyProgramExercises(exerciseProgramId ?? ""),
    enabled: Boolean(exerciseProgramId),
  });

  if (patientQuery.isLoading) {
    return <p className="state-card" role="status">Loading patient portal…</p>;
  }

  if (patientQuery.error) {
    return <p className="state-card" role="alert">Unable to load your patient profile.</p>;
  }

  const patient = patientQuery.data;
  const diagnostics = diagnosticsQuery.data?.items ?? [];
  const programs = programsQuery.data?.items ?? [];
  const doctors = doctorsQuery.data ?? [];
  const selectedProgram = programDetailQuery.data ?? programs.find((program) => program.id === selectedProgramId);
  const exercises = programExercisesQuery.data?.items ?? [];
  const exerciseProgram = exerciseProgramDetailQuery.data ?? programs.find((program) => program.id === exerciseProgramId);
  const recordingExercises = recordingExercisesQuery.data?.items ?? [];

  if (exerciseProgramId) {
    return (
      <section className="patient-portal" aria-label="Patient exercise recording workspace">
        <ExerciseRecordingScreen
          api={api}
          program={exerciseProgram}
          exercises={recordingExercises}
          isLoading={exerciseProgramDetailQuery.isLoading || recordingExercisesQuery.isLoading}
          error={exerciseProgramDetailQuery.error || recordingExercisesQuery.error}
          onBack={() => setExerciseProgramId(undefined)}
          onRecord={setRecordingExercise}
        />
        {recordingExercise ? (
          <RecordingDialog
            api={api}
            exercise={recordingExercise}
            onClose={() => setRecordingExercise(undefined)}
          />
        ) : null}
      </section>
    );
  }

  return (
    <section className="patient-portal v0-patient-portal" aria-label="Patient portal">
      <section className="v0-patient-card" aria-label="Patient summary">
        <div className="v0-card-header">
          <div className="v0-patient-title-block">
            <span className="v0-health-record-label">
              <HeartPulseIcon />
              My health record
            </span>
            <h1>{patient ? `${patient.nombre} ${patient.apellidos}` : "Patient"}</h1>
          </div>
          <span className="v0-secondary-badge">Read-only view</span>
        </div>
        <div className="v0-separator" />
        <dl className="v0-patient-demographics">
          <div>
            <dt>Age</dt>
            <dd>{patient?.birth_date ? `${calculateAge(patient.birth_date)} years` : "—"}</dd>
          </div>
          <div>
            <dt><CalendarIcon /> Date of birth</dt>
            <dd>{patient?.birth_date ? formatDate(patient.birth_date) : "—"}</dd>
          </div>
          <div>
            <dt>Sex</dt>
            <dd>{patient?.sex || "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="v0-patient-section" aria-label="My diagnostic history">
        <div className="v0-section-title">
          <h2>My diagnostics</h2>
          <p>Assessments recorded by your care team.</p>
        </div>
        {diagnosticsQuery.isLoading ? <p className="state-card compact" role="status">Loading diagnostics…</p> : null}
        {diagnostics.length === 0 && !diagnosticsQuery.isLoading ? (
          <div className="v0-empty-card">
            <ClipboardListIcon />
            <p>You have no diagnostics on record yet.</p>
          </div>
        ) : null}
        <div className="v0-diagnostic-list">
          {diagnostics.map((diagnostic) => (
            <article key={diagnostic.id} className="v0-diagnostic-card">
              <div className="v0-diagnostic-card-top">
                <h3>{diagnostic.dolencia}</h3>
                {diagnostic.signed_at ? (
                  <span className="v0-primary-soft-badge"><CheckCircleIcon /> Signed</span>
                ) : (
                  <span className="v0-secondary-badge"><FileEditIcon /> In progress</span>
                )}
              </div>
              <p className="v0-diagnostic-description">{diagnostic.descripcion || "No description documented."}</p>
              {diagnostic.symptoms ? (
                <div className="v0-symptom-list">
                  {diagnostic.symptoms.split(/[;,]/).map((symptom) => symptom.trim()).filter(Boolean).map((symptom) => (
                    <span key={symptom} className="v0-outline-badge">{symptom}</span>
                  ))}
                </div>
              ) : null}
              <p className="v0-date-line">
                {diagnostic.signed_at
                  ? `Signed ${formatDateTime(diagnostic.signed_at)}`
                  : `Recorded ${formatDateTime(diagnostic.created_at)}`}
              </p>
            </article>
          ))}
        </div>
      </section>

      <div className="v0-section-separator" />

      <section className="v0-patient-section" aria-label="My rehabilitation programs">
        <div className="v0-section-title">
          <h2>My rehabilitation programs</h2>
          <p>Exercise plans assigned by your physiotherapist.</p>
        </div>
        {programsQuery.isLoading ? <p className="state-card compact" role="status">Loading programs…</p> : null}
        {programs.length === 0 && !programsQuery.isLoading ? (
          <div className="v0-empty-card">
            <DumbbellIcon />
            <p>You have no rehabilitation programs yet.</p>
          </div>
        ) : null}
        <div className="v0-rehab-program-list">
          {programs.map((program) => (
            <PatientRehabProgramCard
              key={program.id}
              api={api}
              program={program}
              diagnosticName={diagnostics.find((diagnostic) => diagnostic.id === program.diagnostic_id)?.dolencia}
              physiotherapistName={formatPhysiotherapistName(program.physiotherapist_id, doctors)}
              onRecordProgram={() => setExerciseProgramId(program.id)}
            />
          ))}
        </div>
      </section>

      {selectedProgramId && selectedProgram ? (
        <span className="sr-only" aria-label="Selected rehabilitation program">
          {selectedProgram.name || "Untitled rehab program"} {selectedProgram.start_date ? formatDate(selectedProgram.start_date) : ""}
          {exercises.map((exercise) => exercise.pauta || exercise.exercise_id).join(" ")}
        </span>
      ) : null}
    </section>
  );
}

function PatientRehabProgramCard({
  api,
  program,
  diagnosticName,
  physiotherapistName,
  onRecordProgram,
}: {
  api: PatientPortalFeatureApi;
  program: ProgramOut;
  diagnosticName?: string;
  physiotherapistName: string;
  onRecordProgram: () => void;
}) {
  const exercisesQuery = useQuery({
    queryKey: ["patient-portal", "program-card-exercises", program.id],
    queryFn: () => api.listMyProgramExercises(program.id),
  });
  const exercises = exercisesQuery.data?.items ?? [];
  const notes = getProgramNotes(program);

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRecordProgram();
    }
  }

  return (
    <article
      className="v0-rehab-program-card v0-rehab-program-card-clickable"
      role="link"
      tabIndex={0}
      onClick={onRecordProgram}
      onKeyDown={handleKeyDown}
      aria-label={`${program.name || "Untitled rehab program"}: view exercises and record progress`}
    >
      <div className="v0-rehab-card-header">
        <div>
          <div className="v0-rehab-title-row">
            <h3>{program.name || "Untitled rehab program"}</h3>
            {program.estado === "active" ? (
              <span className="v0-primary-soft-badge"><CheckCircleIcon /> Active</span>
            ) : (
              <span className="v0-secondary-badge"><FileEditIcon /> Draft</span>
            )}
          </div>
          <p className="v0-date-line">Assigned {formatDateTime(program.created_at)}</p>
        </div>
      </div>

      <div className="v0-rehab-card-content">
        <div className="v0-separator" />
        <dl className="v0-program-meta-grid">
          <div>
            <dt><UserCogIcon /> Physiotherapist</dt>
            <dd>{physiotherapistName}</dd>
          </div>
          <div>
            <dt><StethoscopeIcon /> For diagnostic</dt>
            <dd>{diagnosticName || program.diagnostic_id}</dd>
          </div>
        </dl>
        {notes ? (
          <div className="v0-program-notes">
            <dt>Notes from your team</dt>
            <dd>{notes}</dd>
          </div>
        ) : null}
        {exercisesQuery.isLoading ? <p className="state-card compact" role="status">Loading exercises…</p> : null}
        {exercises.length > 0 ? <PatientExerciseTable exercises={exercises} /> : null}
        {exercises.length === 0 && !exercisesQuery.isLoading ? <p className="exercise-table-empty">No exercises assigned yet.</p> : null}
      </div>
    </article>
  );
}

function formatPhysiotherapistName(physiotherapistId: string | null | undefined, doctors: DoctorOut[]) {
  if (!physiotherapistId) return "Not assigned";
  const doctor = doctors.find((item) => item.id === physiotherapistId);
  return doctor ? `${doctor.nombre} ${doctor.apellidos}` : physiotherapistId;
}

function getProgramNotes(program: ProgramOut) {
  const value = (program as ProgramOut & { notes?: string | null }).notes;
  return value?.trim() || null;
}

function calculateAge(value: string) {
  const birthDate = new Date(value);
  if (Number.isNaN(birthDate.getTime())) return "—";
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const hasBirthdayPassed =
    today.getMonth() > birthDate.getMonth() ||
    (today.getMonth() === birthDate.getMonth() && today.getDate() >= birthDate.getDate());
  if (!hasBirthdayPassed) age -= 1;
  return age;
}

function ExerciseRecordingScreen({
  api,
  program,
  exercises,
  isLoading,
  error,
  onBack,
  onRecord,
}: {
  api: PatientPortalFeatureApi;
  program?: ProgramOut;
  exercises: ProgramExerciseOut[];
  isLoading: boolean;
  error: unknown;
  onBack: () => void;
  onRecord: (exercise: ProgramExerciseOut) => void;
}) {
  const [selectedExerciseId, setSelectedExerciseId] = useState<string>();

  useEffect(() => {
    if (exercises.length === 0) {
      setSelectedExerciseId(undefined);
      return;
    }
    if (!selectedExerciseId || !exercises.some((exercise) => exercise.id === selectedExerciseId)) {
      setSelectedExerciseId(exercises[0].id);
    }
  }, [exercises, selectedExerciseId]);

  const selectedExercise = exercises.find((exercise) => exercise.id === selectedExerciseId) ?? exercises[0];
  const selectedIndex = selectedExercise ? exercises.findIndex((exercise) => exercise.id === selectedExercise.id) : -1;

  return (
    <section className="detail-card exercise-recording-screen" aria-label="View exercises and record progress">
      <div className="recording-v0-page-header">
        <button type="button" className="recording-v0-back-button" aria-label="Back to rehabilitation program" onClick={onBack}>
          <ArrowLeftIcon />
        </button>
        <div className="recording-v0-title-copy">
          <h2>{program?.name || "Rehabilitation program"}</h2>
          <p>View exercises and record progress</p>
        </div>
        <span className="status-badge">{program?.estado || "active"}</span>
      </div>

      {isLoading ? <p className="state-card compact" role="status">Loading exercises…</p> : null}
      {error ? <p className="state-card compact" role="alert">Unable to load exercises for recording.</p> : null}
      {exercises.length === 0 && !isLoading ? <p className="exercise-table-empty">No exercises assigned yet.</p> : null}

      {exercises.length > 0 ? (
        <div className="recording-progress-layout">
          <aside className="selectable-exercise-panel" aria-label="Selectable exercises">
            <div className="selectable-exercise-panel-header">
              <div>
                <h3>Exercises</h3>
                <p>Select an exercise to view details and recordings.</p>
              </div>
              <span className="status-badge">{exercises.length}</span>
            </div>
            <div className="selectable-exercise-list" role="listbox" aria-label="Assigned exercises">
              {exercises.map((exercise, index) => {
                const isSelected = exercise.id === selectedExercise?.id;
                return (
                  <button
                    key={exercise.id}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    className={isSelected ? "selectable-exercise-item selected" : "selectable-exercise-item"}
                    onClick={() => setSelectedExerciseId(exercise.id)}
                  >
                    <span className="selectable-exercise-copy">
                      <strong>{getExerciseDisplayName(exercise, index)}</strong>
                      <small>{getExerciseCategory(exercise)}</small>
                    </span>
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="selected-exercise-column">
            <section className="selected-exercise-detail" aria-label="Selected exercise description">
              {selectedExercise ? (
                <>
                  <div className="selected-exercise-detail-header">
                    <div>
                      <p className="eyebrow">Selected exercise</p>
                      <h3>{getExerciseDisplayName(selectedExercise, selectedIndex)}</h3>
                      <p>{getExerciseCategory(selectedExercise)}</p>
                    </div>
                  </div>
                  <div className="selected-exercise-description-grid">
                    <div>
                      <span>Sets</span>
                      <strong>—</strong>
                    </div>
                    <div>
                      <span>Reps</span>
                      <strong>—</strong>
                    </div>
                    <div>
                      <span>Frequency</span>
                      <strong>{selectedExercise.pauta || "As prescribed"}</strong>
                    </div>
                    <div className="selected-exercise-description-full">
                      <p>{selectedExercise.pauta || "Follow the assigned rehabilitation exercise and record your progress when complete."}</p>
                    </div>
                  </div>
                </>
              ) : null}
            </section>

            {selectedExercise ? <ExerciseRecordingList api={api} exercise={selectedExercise} onRecord={onRecord} /> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function getExerciseDisplayName(exercise: ProgramExerciseOut, index: number) {
  const label = exercise.exercise_id?.split("-")[0];
  return label ? `Exercise ${index + 1}` : exercise.pauta || `Exercise ${index + 1}`;
}

function getExerciseCategory(exercise: ProgramExerciseOut) {
  return exercise.estado || "Assigned exercise";
}

function ExerciseRecordingList({ api, exercise, onRecord }: { api: PatientPortalFeatureApi; exercise: ProgramExerciseOut; onRecord: (exercise: ProgramExerciseOut) => void }) {
  const recordingsQuery = useQuery({
    queryKey: ["patient-portal", "exercise-recordings", exercise.id],
    queryFn: () => api.listExerciseRecordings(exercise.id),
  });
  const recordings = recordingsQuery.data ?? [];

  return (
    <div className="exercise-recordings-history" aria-label="Exercise recordings">
      <div className="exercise-recordings-heading">
        <div>
          <h4>Recordings</h4>
          <p>Your saved progress entries for this exercise.</p>
        </div>
        <button type="button" className="recording-section-button" onClick={() => onRecord(exercise)}>
          <PlusIcon /> Record
        </button>
      </div>
      {recordingsQuery.isLoading ? <p className="state-card compact" role="status">Loading recordings…</p> : null}
      {recordingsQuery.error ? <p className="state-card compact" role="alert">Unable to load recordings.</p> : null}
      {recordings.length === 0 && !recordingsQuery.isLoading ? <p className="exercise-table-empty">No recordings saved yet.</p> : null}
      {recordings.length > 0 ? <ExerciseRecordingsTable recordings={recordings} /> : null}
    </div>
  );
}

function ExerciseRecordingsTable({ recordings }: { recordings: ExerciseRecordingListItem[] }) {
  return (
    <div className="table-scroll recording-history-scroll">
      <table className="recording-history-table">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Type</th>
            <th scope="col">Duration</th>
            <th scope="col">Notes</th>
          </tr>
        </thead>
        <tbody>
          {recordings.map((recording) => (
            <tr key={recording.recording_id}>
              <td>{formatDateTime(recording.recording_date || recording.created_at)}</td>
              <td><RecordingTypeLabel type={recording.media_kind} /></td>
              <td>{formatRecordingDuration(recording.duration_seconds)}</td>
              <td>{recording.notes || recording.media_status || "Progress recording saved"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecordingTypeLabel({ type }: { type?: string | null }) {
  const normalized = type === "video" ? "video" : "audio";
  return (
    <span className="recording-type-label">
      {normalized === "video" ? <VideoIcon /> : <AudioIcon />}
      <span>{formatRecordingType(normalized)}</span>
    </span>
  );
}

function PatientExerciseTable({ exercises }: { exercises: ProgramExerciseOut[] }) {
  return (
    <div className="v0-program-exercise-table-wrap">
      <table className="v0-program-exercise-table">
        <thead>
          <tr>
            <th scope="col">Exercise</th>
            <th scope="col">Category</th>
            <th scope="col" className="centered">Sets</th>
            <th scope="col" className="centered">Reps</th>
            <th scope="col">Frequency</th>
          </tr>
        </thead>
        <tbody>
          {exercises.map((exercise, index) => (
            <tr key={exercise.id}>
              <td className="exercise-name-cell">
                {getExerciseDisplayName(exercise, index)}
                {exercise.pauta ? <span>{exercise.pauta}</span> : null}
              </td>
              <td><span className="v0-outline-badge">{getExerciseCategory(exercise)}</span></td>
              <td className="centered">—</td>
              <td className="centered">—</td>
              <td>{exercise.pauta || "As prescribed"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RecordingDialog({ api, exercise, onClose }: { api: PatientPortalFeatureApi; exercise: ProgramExerciseOut; onClose: () => void }) {
  const [hasConsent, setHasConsent] = useState(false);
  const [status, setStatus] = useState<"idle" | "recording" | "recorded" | "saving" | "saved" | "error">("idle");
  const [duration, setDuration] = useState(0);
  const [mediaBlob, setMediaBlob] = useState<Blob>();
  const [mediaKind, setMediaKind] = useState<"audio" | "video">("audio");
  const [uploadedFile, setUploadedFile] = useState<File>();
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [recordingId, setRecordingId] = useState<string>();
  const [error, setError] = useState<string>();
  const queryClient = useQueryClient();
  const recorderRef = useRef<MediaRecorder>();
  const streamRef = useRef<MediaStream>();
  const chunksRef = useRef<BlobPart[]>([]);
  const startedAtRef = useRef<number>(0);
  const sampleRateRef = useRef<number>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let timer: number | undefined;
    if (status === "recording") {
      timer = window.setInterval(() => {
        setDuration(Math.max(0, Math.round((Date.now() - startedAtRef.current) / 1000)));
      }, 500);
    }
    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, [status]);

  useEffect(() => () => stopStream(streamRef.current), []);

  useEffect(() => {
    if (!mediaBlob) {
      setPreviewUrl(undefined);
      return;
    }
    const url = URL.createObjectURL(mediaBlob);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [mediaBlob]);

  async function startRecording() {
    setError(undefined);
    if (!hasConsent) {
      setError("Please confirm consent before recording.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Audio recording is not supported by this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      sampleRateRef.current = stream.getAudioTracks()[0]?.getSettings().sampleRate;
      chunksRef.current = [];
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const type = recorder.mimeType || "audio/webm";
        setMediaBlob(new Blob(chunksRef.current, { type }));
        setMediaKind("audio");
        setUploadedFile(undefined);
        setDuration(Math.max(0, (Date.now() - startedAtRef.current) / 1000));
        setStatus("recorded");
        stopStream(stream);
      };
      startedAtRef.current = Date.now();
      setDuration(0);
      recorder.start();
      setStatus("recording");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to access microphone.");
      setStatus("error");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
  }

  function resetMedia() {
    setMediaBlob(undefined);
    setUploadedFile(undefined);
    setDuration(0);
    setRecordingId(undefined);
    setStatus("idle");
    setError(undefined);
    sampleRateRef.current = undefined;
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleFileSelect(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("audio/") && !file.type.startsWith("video/")) {
      setError("Please select an audio or video file.");
      event.target.value = "";
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      setError("File size must be less than 100 MB.");
      event.target.value = "";
      return;
    }
    setError(undefined);
    setRecordingId(undefined);
    setUploadedFile(file);
    setMediaBlob(file);
    setMediaKind(file.type.startsWith("video/") ? "video" : "audio");
    setDuration(0);
    sampleRateRef.current = undefined;
    setStatus("recorded");
  }

  async function saveRecording() {
    if (!mediaBlob) return;
    setStatus("saving");
    setError(undefined);
    try {
      const contentType = mediaBlob.type || "audio/webm";
      const sha256 = await sha256Hex(mediaBlob);
      const upload = await api.createRecordingUploadUrl({ program_exercise_id: exercise.id, content_type: contentType });
      await api.uploadRecordingBlob(upload.url, mediaBlob, contentType);
      const saved = await api.registerRecording({
        program_exercise_id: exercise.id,
        storage_uri: upload.key,
        content_type: upload.content_type || contentType,
        duration_seconds: duration,
        sample_rate: sampleRateRef.current,
        size_bytes: mediaBlob.size,
        sha256,
      });
      setRecordingId(saved.recording_id);
      await queryClient.invalidateQueries({ queryKey: ["patient-portal", "exercise-recordings", exercise.id] });
      setStatus("saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the recording.");
      setStatus("error");
    }
  }

  const canSave = status === "recorded" && Boolean(mediaBlob);
  const isSaving = status === "saving";

  return (
    <div className="recording-dialog-backdrop" role="presentation">
      <section className="recording-dialog" role="dialog" aria-modal="true" aria-labelledby="recording-dialog-title">
        <div className="recording-dialog-header">
          <div>
            <p className="eyebrow">Record exercise</p>
            <h2 id="recording-dialog-title">Record progress</h2>
            <p>Record now or upload an audio/video file. Voice is sensitive biometric data.</p>
          </div>
          <button type="button" className="dialog-close-button" aria-label="Close recording dialog" onClick={onClose}>×</button>
        </div>

        <div className="recording-dialog-body">
          <div className="recording-target-card">
            <strong>{exercise.pauta || "Assigned exercise"}</strong>
            <span>Exercise ID {exercise.exercise_id}</span>
          </div>

          <label className="recording-consent">
            <input type="checkbox" checked={hasConsent} onChange={(event) => setHasConsent(event.target.checked)} />
            <span>I consent to recording or uploading my voice/audio for this rehabilitation exercise.</span>
          </label>

          <div className={status === "recording" ? "recording-pulse active" : "recording-pulse"} aria-live="polite">
            <span aria-hidden="true" />
            <strong>{status === "recording" ? "Recording" : status === "saved" ? "Recording saved" : uploadedFile ? "File ready" : "Ready to record"}</strong>
            <small>{formatDuration(duration)}</small>
          </div>

          {previewUrl && status !== "recording" ? mediaKind === "video" ? (
            <video className="recording-playback recording-video-playback" controls src={previewUrl} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}>
              <track kind="captions" />
            </video>
          ) : (
            <audio className="recording-playback" controls src={previewUrl} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || duration)}>
              <track kind="captions" />
            </audio>
          ) : null}

          {uploadedFile ? (
            <div className="recording-upload-info">
              <strong>File uploaded</strong>
              <span>{uploadedFile.name} ({formatFileSize(uploadedFile.size)})</span>
            </div>
          ) : null}

          <input
            ref={fileInputRef}
            className="recording-file-input"
            type="file"
            accept="audio/*,video/*"
            aria-label="Upload audio or video file"
            onChange={handleFileSelect}
          />

          {recordingId ? <p className="recording-success">Exercise Recording registered: {recordingId}</p> : null}
          {error ? <p className="recording-error" role="alert">{error}</p> : null}
        </div>

        <div className="recording-dialog-actions">
          {status === "recording" ? (
            <button type="button" className="v0-outline-button" onClick={stopRecording}>Stop</button>
          ) : mediaBlob ? (
            <button type="button" className="v0-outline-button" disabled={isSaving} onClick={resetMedia}>Retry</button>
          ) : (
            <>
              <button type="button" className="record-button" disabled={!hasConsent || isSaving} onClick={startRecording}>
                <RecordIcon /> Record
              </button>
              <button type="button" className="v0-outline-button recording-upload-button" disabled={!hasConsent || isSaving} onClick={() => fileInputRef.current?.click()}>
                <UploadFileIcon /> Upload file
              </button>
            </>
          )}
          <button type="button" className="v0-primary-button" disabled={!canSave || isSaving} onClick={saveRecording}>
            {isSaving ? "Saving…" : "Save recording"}
          </button>
        </div>
      </section>
    </div>
  );
}

async function sha256Hex(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function pickMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/wav"];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
}

function stopStream(stream?: MediaStream) {
  stream?.getTracks().forEach((track) => track.stop());
}

function getInitials(label: string) {
  return label
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("") || "P";
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatRecordingType(value?: string | null) {
  if (!value) return "Audio";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatRecordingDuration(seconds?: number | null) {
  if (seconds == null) return "—";
  return formatDuration(seconds);
}

function formatFileSize(sizeBytes: number) {
  return `${(sizeBytes / 1024 / 1024).toFixed(2)} MB`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);
}

function formatDuration(seconds: number) {
  const mins = Math.floor(seconds / 60).toString().padStart(2, "0");
  const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function HeartPulseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M19.5 13.5 12 21l-7.5-7.5a5 5 0 0 1 7.1-7.1l.4.4.4-.4a5 5 0 0 1 7.1 7.1Z" />
      <path d="M3 12h4l2-4 3 8 2-4h7" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M8 2v4" />
      <path d="M16 2v4" />
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M3 10h18" />
    </svg>
  );
}

function CheckCircleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="9" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function FileEditIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <path d="m12 18 4-4 2 2-4 4h-2v-2Z" />
    </svg>
  );
}

function ClipboardListIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M9 5h6" />
      <path d="M9 3h6a2 2 0 0 1 2 2v1h1a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h1V5a2 2 0 0 1 2-2Z" />
      <path d="M8 12h.01" />
      <path d="M11 12h5" />
      <path d="M8 16h.01" />
      <path d="M11 16h5" />
    </svg>
  );
}

function DumbbellIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="m6.5 6.5 11 11" />
      <path d="m4 9 5-5" />
      <path d="m15 20 5-5" />
      <path d="m2 11 9-9" />
      <path d="m13 22 9-9" />
    </svg>
  );
}

function UserCogIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="9" cy="7" r="4" />
      <path d="M2 21a7 7 0 0 1 11-5.7" />
      <circle cx="18" cy="18" r="3" />
      <path d="M18 13.5V15" />
      <path d="M18 21v1.5" />
      <path d="m21.2 16.1-1.3.75" />
      <path d="m16.1 19.15-1.3.75" />
    </svg>
  );
}

function StethoscopeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M6 3v5a4 4 0 0 0 8 0V3" />
      <path d="M8 3H5" />
      <path d="M15 3h-3" />
      <path d="M10 12v3a5 5 0 0 0 10 0v-1" />
      <circle cx="20" cy="10" r="2" />
    </svg>
  );
}

function ArrowLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function AudioIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <path d="M12 19v3" />
    </svg>
  );
}

function VideoIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M15 10l5-3v10l-5-3v-4Z" />
      <rect x="3" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function RecordIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="6" />
    </svg>
  );
}

function UploadFileIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <path d="M12 18v-6" />
      <path d="m9 15 3-3 3 3" />
    </svg>
  );
}
