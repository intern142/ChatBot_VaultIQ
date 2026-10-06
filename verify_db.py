import psycopg2

conn = psycopg2.connect('postgresql://vaultiq:vaultiq_secret@localhost:5433/vaultiq')
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
print('Tables:', [row[0] for row in cur.fetchall()])

cur.execute("SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()