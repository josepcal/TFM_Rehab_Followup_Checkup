"""UC4 seed metric_definition for sustained_phonation_v1 (schema-aligned)

Revision ID: uc4_seed_metric_definition
Revises: 
Create Date: 2026-01-01
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'uc4_seed_metric_definition'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    INSERT INTO setup.metric_definition (
        analysis_setup_id,
        path,
        label,
        section,
        value_kind,
        unit,
        data_type,
        nullable,
        display_order
    )
    SELECT
        s.analysis_setup_id,
        v.path,
        v.label,
        'raw',
        'raw',
        v.unit,
        'float',
        false,
        v.display_order
    FROM setup.analysis_setup s
    CROSS JOIN (
        VALUES
            ('raw.phonation_duration_sec', 'Phonation Duration', 's', 1),
            ('raw.jitter_local_pct', 'Jitter (local)', '%', 2),
            ('raw.shimmer_local_pct', 'Shimmer (local)', '%', 3),
            ('raw.hnr_db', 'Harmonics-to-Noise Ratio', 'dB', 4),
            ('raw.volume_std_db', 'Volume Std Dev', 'dB', 5)
    ) AS v(path, label, unit, display_order)
    WHERE s.metric_api_endpoint = 'sustained_phonation_v1'
    ON CONFLICT (analysis_setup_id, path) DO NOTHING;
    """)


def downgrade():
    op.execute("""
    DELETE FROM setup.metric_definition
    WHERE path IN (
        'raw.phonation_duration_sec',
        'raw.jitter_local_pct',
        'raw.shimmer_local_pct',
        'raw.hnr_db',
        'raw.volume_std_db'
    )
    AND analysis_setup_id IN (
        SELECT analysis_setup_id
        FROM setup.analysis_setup
        WHERE metric_api_endpoint = 'sustained_phonation_v1'
    );
    """)
