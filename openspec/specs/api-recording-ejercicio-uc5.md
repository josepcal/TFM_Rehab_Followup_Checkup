# API Specification: Recording Ejercicio (UC-05)

## Purpose

Define backend behavior for exercise recording upload URL creation, metadata registration and authorized read access.

## Requirements

### Requirement: Create recording upload target

The system MUST allow an authenticated patient to request an upload target for an assigned exercise in one of their rehab programs.

#### Scenario: Patient requests upload URL for owned exercise

- GIVEN an authenticated patient and a program exercise belonging to one of their rehab programs
- WHEN `POST /recordings/upload-url` is sent with `program_exercise_id` and `content_type`
- THEN the API returns an upload key/URI and URL for a supported audio/video content type.

#### Scenario: Reject unowned exercise

- GIVEN an authenticated patient and a program exercise belonging to another patient
- WHEN `POST /recordings/upload-url` is requested
- THEN the API returns `403` or `404` without exposing the other patient's data.

#### Scenario: Reject unsupported media

- GIVEN an authenticated patient and an owned program exercise
- WHEN `POST /recordings/upload-url` is sent with a non-audio/video `content_type`
- THEN the API returns `422` or `400` and no upload target is created.

### Requirement: Register recording metadata

The system MUST register a Recording entity after media upload without storing raw media in PostgreSQL.

#### Scenario: Register uploaded recording

- GIVEN an authenticated patient, an owned program exercise and a successful object-storage upload
- WHEN `POST /recordings/` is sent with `program_exercise_id`, `storage_uri` and `content_type`
- THEN the API returns `201` with `recording_id`
- AND the Recording row references the program exercise and storage URI.

#### Scenario: Reject storage URI not associated with requested exercise

- GIVEN an authenticated patient and an owned program exercise
- WHEN `POST /recordings/` references a malformed or unrelated `storage_uri`
- THEN the API rejects the request.

### Requirement: Read recordings by authorization

The system MUST let authorized users list/read recordings for a program exercise and MUST prevent cross-patient access.

#### Scenario: Patient lists own exercise recordings

- GIVEN an authenticated patient and an owned program exercise
- WHEN `GET /program-exercises/{program_exercise_id}/recordings` is requested
- THEN the API returns only recordings for that program exercise.

#### Scenario: Medical user reads authorized patient recording

- GIVEN an authenticated medical user authorized for the patient's rehab program
- WHEN the user requests the recording list or detail
- THEN the API returns the requested metadata.

#### Scenario: Reject cross-patient read

- GIVEN an authenticated patient
- WHEN the patient requests recordings for another patient's exercise
- THEN the API returns `403` or `404`.

### Requirement: Privacy-preserving media storage

The system MUST keep raw recording bytes outside the relational medical database.

#### Scenario: Persist metadata only

- GIVEN a recording registration request
- WHEN the Recording row is created
- THEN PostgreSQL stores identifiers, timestamps, storage URI/key and content type
- AND does not store the raw audio/video blob.
