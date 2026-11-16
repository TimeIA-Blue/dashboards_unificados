def create_db(conn):
    cursor = conn.cursor()
    # lendo sql/create.sql
    f = open("sql/create.sql", "r")
    sql = f.read()
    f.close()
    # criando tabelas
    cursor.executescript(sql)
    conn.commit()
