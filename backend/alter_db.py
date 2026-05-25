import sqlite3

conn = sqlite3.connect("grader.db")
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE experiments ADD COLUMN short_code VARCHAR;")
except sqlite3.OperationalError:
    print("short_code already exists")

try:
    cursor.execute("ALTER TABLE experiments ADD COLUMN max_marks FLOAT;")
except sqlite3.OperationalError:
    print("max_marks already exists")

conn.commit()
conn.close()
print("Migration completed.")
