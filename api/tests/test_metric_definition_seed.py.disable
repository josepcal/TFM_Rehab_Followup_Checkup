
from app.analysis.models import AnalysisSetup


def test_sustained_phonation_metric_definitions_exist(db_session):
    setup = (
        db_session.query(AnalysisSetup)
        .filter(
            AnalysisSetup.metric_api_endpoint == "sustained_phonation_v1"
        )
        .one()
    )

    paths = {md.path for md in setup.metric_definitions}

    assert paths == {
        "raw.phonation_duration_sec",
        "raw.jitter_local_pct",
        "raw.shimmer_local_pct",
        "raw.hnr_db",
        "raw.volume_std_db",
    }
