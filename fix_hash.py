import asyncio
import asyncpg

async def fix_hash():
    conn = await asyncpg.connect('postgresql://vaultiq:vaultiq_secret@localhost:5433/vaultiq')
    hash_val = '$2b$12$zsw04wSSkIH7lEpiECvqZuyuyI4NEdCQ./IfzKJgJ0JcMcFeFAu86'
    await conn.execute('UPDATE users SET password_hash = $1 WHERE email = $2', hash_val, 'usera@tenant_a.com')
    await conn.execute('UPDATE users SET password_hash = $1 WHERE email = $2', hash_val, 'userb@tenant_b.com')
    await conn.close()

asyncio.run(fix_hash())
print('Done')