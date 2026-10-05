import psycopg2

conn = psycopg2.connect('postgresql://vaultiq:vaultiq_secret@localhost:5433/vaultiq')
cur = conn.cursor()
cur.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
conn.commit()
cur.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
cur.execute("INSERT INTO alembic_version VALUES ('006_sessions_tenant_nullable')")
conn.commit()
print('stamped')