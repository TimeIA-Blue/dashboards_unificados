def create_db(conn):
    cursor = conn.cursor()
    # lendo sql/create.sql
    with open("sql/create.sql", "r") as f:
        sql = f.read()
    # criando tabelas
    cursor.executescript(sql)
    conn.commit()
