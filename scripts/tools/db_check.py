import sqlite3
db_path = r'D:\元初系统\天机v9.1\data\icme.db'
c = sqlite3.connect(db_path)
result = c.execute('PRAGMA integrity_check').fetchone()
print('DB Integrity:', result)
# Check FTS tables
cursor = c.execute(" SELECT name FROM sqlite_master WHERE type=table AND name LIKE %fts% \)
fts_tables = cursor.fetchall()
print('FTS Tables:', fts_tables)
c.close()
