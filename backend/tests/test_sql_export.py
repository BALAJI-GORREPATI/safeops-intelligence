import uuid
from sqlalchemy.schema import CreateTable
from safeops.db import engine
from safeops.models import Base
from safeops.generator import generate, GeneratorConfig
from safeops.artifacts import export_dataset


def test_postgresql_sql_seed_round_trip_in_isolated_transaction(tmp_path):
    data = generate(GeneratorConfig())
    export_dataset(data, GeneratorConfig(), {}, tmp_path)
    sql = (tmp_path/'sql/seed.sql').read_text(encoding='utf-8')
    statements = sql.splitlines()[2:-1]
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = 'artifact_test_'+uuid.uuid4().hex[:12]
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            for table in Base.metadata.sorted_tables:
                connection.execute(CreateTable(table))
            for statement in statements: connection.exec_driver_sql(statement)
            assert connection.exec_driver_sql('SELECT count(*) FROM alarm_events').scalar_one() == 800
            assert connection.exec_driver_sql('SELECT count(*) FROM ground_truth').scalar_one() == 5
            assert connection.exec_driver_sql('SELECT count(*) FROM incidents').scalar_one() == len(data['incidents'])
        finally:
            transaction.rollback()
