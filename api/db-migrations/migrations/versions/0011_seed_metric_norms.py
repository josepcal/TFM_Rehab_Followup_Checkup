"""seed reference.metric_norm with 11 dysarthria analysis norms (UC-09 extension)

Revision ID: 0011_seed_metric_norms
Revises: 0010_followup_checkup
"""

from alembic import op

revision = "0011_seed_metric_norms"
down_revision = "0010_followup_checkup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO reference.metric_norm (
            metric_code, label, unit, direction,
            sex, age_min, age_max,
            good_min, good_max, poor_min, poor_max,
            source, version
        ) VALUES
            ('phonation_duration_sec', 'Phonation Duration', 'sec', 'higher_better',
             NULL, NULL, NULL, 15.0, NULL, NULL, 6.0, 'dysarthria_analysis_v1', 1),
            ('jitter_local_pct', 'Jitter (local)', '%', 'lower_better',
             NULL, NULL, NULL, NULL, 1.04, 3.0, NULL, 'dysarthria_analysis_v1', 1),
            ('shimmer_local_pct', 'Shimmer (local)', '%', 'lower_better',
             NULL, NULL, NULL, NULL, 3.81, 10.0, NULL, 'dysarthria_analysis_v1', 1),
            ('hnr_db', 'HNR', 'dB', 'higher_better',
             NULL, NULL, NULL, 20.0, NULL, NULL, 7.0, 'dysarthria_analysis_v1', 1),
            ('volume_std_db_sustain', 'Volume Stability', 'dB', 'lower_better',
             NULL, NULL, NULL, NULL, 1.5, 6.0, NULL, 'dysarthria_analysis_v1', 1),
            ('ddk_rate_syll_sec', 'DDK Rate', 'syll/s', 'higher_better',
             NULL, NULL, NULL, 6.0, NULL, NULL, 3.0, 'dysarthria_analysis_v1', 1),
            ('ddk_cv_interval', 'DDK Regularity', '', 'lower_better',
             NULL, NULL, NULL, NULL, 0.10, 0.35, NULL, 'dysarthria_analysis_v1', 1),
            ('labial_mod_depth', 'Labial Closure', '', 'higher_better',
             NULL, NULL, NULL, 0.85, NULL, NULL, 0.35, 'dysarthria_analysis_v1', 1),
            ('lingual_mod_depth', 'Lingual Closure', '', 'higher_better',
             NULL, NULL, NULL, 0.85, NULL, NULL, 0.35, 'dysarthria_analysis_v1', 1),
            ('smr_rate_syll_sec', 'SMR Rate', 'syll/s', 'higher_better',
             NULL, NULL, NULL, 5.0, NULL, NULL, 2.5, 'dysarthria_analysis_v1', 1),
            ('intelligibility_pct', 'Intelligibility', '%', 'higher_better',
             NULL, NULL, NULL, 95.0, NULL, NULL, 50.0, 'dysarthria_analysis_v1', 1)
        ON CONFLICT (metric_code, sex, age_min, age_max, version) DO NOTHING;
        """
    )

    op.execute(
        """
        GRANT SELECT ON reference.metric_norm
            TO ftm_gp, ftm_medical_specialist, ftm_patient, ftm_technician, ftm_ai;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM reference.metric_norm WHERE source = 'dysarthria_analysis_v1';
        """
    )
