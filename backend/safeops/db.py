import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://safeops:safeops_local@127.0.0.1:5432/safeops")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"})
Session = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with Session() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
