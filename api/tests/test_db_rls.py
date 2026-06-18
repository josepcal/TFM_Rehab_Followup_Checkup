from app.context import current_role, current_user
from app.db import _apply_rls


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, identity_id=None):
        self.identity_id = identity_id
        self.calls = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params or {}))
        if "clinical.identity_id_for_subject" in sql:
            return FakeResult(self.identity_id)
        return FakeResult(None)


def _set_context(user="idp|patient-default", role="patient"):
    user_token = current_user.set(user)
    role_token = current_role.set(role)
    return user_token, role_token


def _reset_context(tokens):
    user_token, role_token = tokens
    current_user.reset(user_token)
    current_role.reset(role_token)


def test_apply_rls_sets_identity_id_from_external_subject():
    tokens = _set_context()
    session = FakeSession(identity_id="11111111-1111-1111-1111-111111111111")

    try:
        _apply_rls(session)
    finally:
        _reset_context(tokens)

    assert any("set_config('app.user'" in sql for sql, _ in session.calls)
    assert any("clinical.identity_id_for_subject" in sql for sql, _ in session.calls)
    assert any(
        "set_config('app.identity_id'" in sql
        and params["identity_id"] == "11111111-1111-1111-1111-111111111111"
        for sql, params in session.calls
    )
    assert any("set_config('app.role'" in sql for sql, _ in session.calls)
    assert any("SET LOCAL ROLE ftm_patient" in sql for sql, _ in session.calls)


def test_apply_rls_does_not_set_invalid_identity_when_subject_is_unknown():
    tokens = _set_context(user="idp|missing")
    session = FakeSession(identity_id=None)

    try:
        _apply_rls(session)
    finally:
        _reset_context(tokens)

    assert any("clinical.identity_id_for_subject" in sql for sql, _ in session.calls)
    assert not any("set_config('app.identity_id'" in sql for sql, _ in session.calls)


def test_apply_rls_switches_medical_users_to_specialist_db_role():
    tokens = _set_context(user="idp|doctor-default", role="medical")
    session = FakeSession(identity_id="22222222-2222-2222-2222-222222222222")

    try:
        _apply_rls(session)
    finally:
        _reset_context(tokens)

    assert any("SET LOCAL ROLE ftm_medical_specialist" in sql for sql, _ in session.calls)


def test_apply_rls_prefers_explicit_principal_over_contextvars():
    tokens = _set_context(user="stale-user", role="patient")
    session = FakeSession(identity_id="33333333-3333-3333-3333-333333333333")

    try:
        _apply_rls(session, {"sub": "idp|doctor-default", "role": "medical"})
    finally:
        _reset_context(tokens)

    assert any(params.get("u") == "idp|doctor-default" for _, params in session.calls)
    assert any("SET LOCAL ROLE ftm_medical_specialist" in sql for sql, _ in session.calls)
    assert not any("SET LOCAL ROLE ftm_patient" in sql for sql, _ in session.calls)
