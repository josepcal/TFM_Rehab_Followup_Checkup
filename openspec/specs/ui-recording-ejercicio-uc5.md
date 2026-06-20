# UI Specification: Recording Ejercicio (UC-05)

## Purpose

Define the patient-facing browser flow for recording assigned rehab exercises and registering the resulting Recording entity.

## Requirements

### Requirement: Enter exercise recording screen

The UI MUST let a patient open a dedicated exercise-recording screen from a rehab program detail.

#### Scenario: Open recording screen

- GIVEN a patient is authenticated and viewing one of their rehab programs
- WHEN the patient clicks “View exercises and record progress”
- THEN the UI shows the program exercises and record actions.

#### Scenario: Return to rehab program detail

- GIVEN a patient is on the exercise-recording screen
- WHEN the patient clicks the back action
- THEN the UI returns to the rehab program detail.

### Requirement: Record exercise with consent

The UI MUST require explicit consent before capturing media.

#### Scenario: Consent gates recording

- GIVEN a patient opens the recording dialog for an exercise
- WHEN consent is not checked
- THEN the start recording action is disabled or rejected.

#### Scenario: Capture and stop recording

- GIVEN consent is checked and the browser supports recording
- WHEN the patient starts and then stops recording
- THEN the UI shows a preview/ready-to-upload state.

#### Scenario: Unsupported browser

- GIVEN the browser does not support `MediaRecorder` or `getUserMedia`
- WHEN the patient opens the recording dialog
- THEN the UI shows a clear unsupported-browser message.

### Requirement: Upload and register recording

The UI MUST upload captured or selected audio/video media and register metadata through the API.

#### Scenario: Select an existing media file

- GIVEN the patient has confirmed consent
- WHEN the patient selects an audio/video file up to 100 MB
- THEN the UI previews the file and saves it through the same upload and registration flow.

#### Scenario: Successful upload and registration

- GIVEN the patient has captured a recording
- WHEN the patient saves it
- THEN the UI requests an upload URL, uploads the blob, registers the recording and shows success.

#### Scenario: Upload failure

- GIVEN the patient has captured a recording
- WHEN upload URL creation, blob upload or metadata registration fails
- THEN the UI shows an error and lets the patient retry or close.

### Requirement: Privacy-safe UI behavior

The UI MUST not send raw recording media to non-storage/LLM services.

#### Scenario: Upload target only

- GIVEN a captured blob
- WHEN the UI saves the recording
- THEN raw bytes are sent only to the upload URL returned by the backend.
