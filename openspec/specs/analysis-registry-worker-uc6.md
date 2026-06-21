# API Specification: Analysis Function Registry + Worker (UC-06 infra)

## Purpose

Define backend behavior for registering audio-analysis functions by name, triggering asynchronous execution against a recording, and persisting the result without interpreting its semantics.

## Requirements

### Requirement: Register analysis functions by name

The system MUST resolve a previously deployed analysis function by its registered name and MUST reject execution requests for unregistered names.

#### Scenario: Resolve a registered function

- GIVEN a function decorated with `@register_analysis("sustained_phonation_v1")` at process start
- WHEN the worker resolves `"sustained_phonation_v1"` from the registry
- THEN it returns the corresponding callable.

#### Scenario: Reject unknown function name

- GIVEN a `function_name` that was never registered
- WHEN a job referencing it is dequeued
- THEN the worker raises `UnknownAnalysisFunction` and persists `metric_result` with `status=error`
- AND no `raw_json` is persisted.

### Requirement: Trigger analysis asynchronously without blocking the API

The system MUST let an authorized patient or medical user trigger analysis of a recording and MUST respond without waiting for execution to complete.

#### Scenario: Patient triggers analysis on own recording

- GIVEN an authenticated patient and a recording belonging to one of their program exercises
- WHEN `POST /recordings/{id}/run` is sent
- THEN the API enqueues a job and returns immediately
- AND the recording's analysis state becomes pending until the worker processes it.

#### Scenario: Medical user triggers analysis

- GIVEN an authenticated medical user authorized for the patient's program
- WHEN `POST /recordings/{id}/run` is sent for that recording
- THEN the API enqueues a job and returns immediately.

#### Scenario: Reject technician trigger

- GIVEN an authenticated technician
- WHEN `POST /recordings/{id}/run` is sent
- THEN the API returns `403` and no job is enqueued.

#### Scenario: Function name resolution

- GIVEN a recording whose program exercise has an `analysis_setup.function_name` configured
- WHEN `POST /recordings/{id}/run` is sent without an explicit `function_name`
- THEN the API enqueues the job using the exercise's configured function
- AND an explicit `function_name` in the request body overrides it.

### Requirement: Execute with timeout and error isolation

The system MUST bound the execution time of an analysis function and MUST capture any exception without crashing the worker process.

#### Scenario: Function exceeds timeout

- GIVEN a registered function that runs longer than the configured timeout
- WHEN the worker executes the corresponding job
- THEN execution is aborted
- AND `metric_result.status` is set to `error` with a timeout-related `error_detail`
- AND the worker continues processing subsequent jobs.

#### Scenario: Function raises an exception

- GIVEN a registered function that raises during execution
- WHEN the worker executes the corresponding job
- THEN the exception is caught
- AND `metric_result.status` is set to `error` with the exception detail
- AND the worker continues processing subsequent jobs.

### Requirement: Persist metrics under pseudonym without semantic interpretation

The system MUST persist whatever dict a successful function execution returns, without inspecting or validating the meaning of individual fields, tagged to the patient's pseudonym rather than their identity.

#### Scenario: Successful execution persists raw and flattened metrics

- GIVEN a registered function that returns `{"phonation_seconds": 12.4, "f0_stability": 0.91}`
- WHEN the worker executes it successfully
- THEN `metric_result.raw_json` stores the dict verbatim
- AND `recording_metric` stores the flattened key/value rows
- AND both are tagged with `pseudonym_id`, not the patient's identity
- AND `function_name`, `function_version` and `code_sha` are recorded alongside the result.

### Requirement: Reanalysis overwrites, no automatic retry

The system MUST NOT automatically retry a failed job, and re-triggering analysis on the same recording MUST overwrite the previous result rather than create a history entry.

#### Scenario: Manual reanalysis overwrites prior result

- GIVEN a recording with an existing `metric_result`
- WHEN `POST /recordings/{id}/run` is triggered again
- THEN the existing `metric_result` row is updated in place
- AND no second row is created for the same `recording_id`.

#### Scenario: No automatic retry after failure

- GIVEN a job that failed with `status=error`
- WHEN no one explicitly re-triggers `POST /recordings/{id}/run`
- THEN the worker does not requeue or retry the job on its own.
