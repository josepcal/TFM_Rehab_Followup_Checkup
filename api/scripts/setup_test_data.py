import asyncio
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.clinical.models import Patient, Doctor, CareAssignment, Diagnostic, RehabProgram
from app.catalog.models import RehabExercise
from app.db import Base

DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/tfm_db"  # Adjust connection

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def setup_test_data():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Create tables
            await session.run_sync(Base.metadata.create_all)

            # Create doctors
            doctor_id = uuid.uuid4()
            doctor = Doctor(id=doctor_id, keycloak_id=str(doctor_id), colegiado_id="12345", nombre="Dr. Test", apellidos="Tester")
            session.add(doctor)

            # Create patients
            patient_id = uuid.uuid4()
            patient = Patient(id=patient_id, nombre="Paciente", apellidos="Prueba")
            session.add(patient)

            # Assign doctor to patient
            assignment = CareAssignment(doctor_keycloak_id=str(doctor_id), patient_id=patient.id)
            session.add(assignment)

            # Create a diagnostic
            diagnostic = Diagnostic(id=uuid.uuid4(), patient_id=patient.id, doctor_id=doctor.id, dolencia="Dolencia prueba", descripcion="Descripcion prueba", created_at=datetime.utcnow())
            session.add(diagnostic)

            # Create RehabExercise (catalog)
            rehab_exercise = RehabExercise(id=uuid.uuid4(), nombre="Ejercicio prueba", descripcion="Descripcion ejercicio", tipo="tipo1")
            session.add(rehab_exercise)

            # Create RehabProgram
            rehab_program = RehabProgram(id=uuid.uuid4(), diagnostic_id=diagnostic.id, estado="activo", created_at=datetime.utcnow())
            session.add(rehab_program)

        await session.commit()

    print("Test data setup complete.")

if __name__ == "__main__":
    asyncio.run(setup_test_data())
