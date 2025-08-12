from database import get_db

db = get_db()
db.connect()
result = db.execute_query('DESCRIBE spells')
for r in result:
    print(f"{r['Field']}: {r['Type']}")
