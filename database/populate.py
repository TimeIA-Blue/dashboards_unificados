import pandas as pd


def populate_db(conn):
    cursor = conn.cursor()
    # concessionarias
    if cursor.execute("SELECT COUNT(*) FROM concessionaria").fetchone()[0] > 0:
        print("Banco de dados já populado.")
        return

    df = pd.read_csv("default_data/concessionarias.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO concessionaria (cnpj, no_fantasia)
            VALUES (?, ?)
        """,
            (row.cnpj, row.no_fantasia),  # ty: ignore[missing-attribute]
        )

    # enums de pedagio
    df = pd.read_csv("default_data/pedagio_tipo.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO pedagio_tipo (nome)
            VALUES (?)
        """,
            (row.nome,),  # ty: ignore[missing-attribute]
        )

    # pedagio
    df = pd.read_csv("default_data/pedagio.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO pedagio (cnpj, tipo_interrup, tempo_max_interrup)
            VALUES (?, ?, ?)
        """,
            (row.cnpj, row.tipo_interrup, row.tempo_max_interrup),  # ty: ignore[missing-attribute]
        )

    # enums de radar
    df = pd.read_csv("default_data/radar_tipo.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO radar_tipo (nome)
            VALUES (?)
        """,
            (row.nome,),  # ty: ignore[missing-attribute]
        )

    # radar
    df = pd.read_csv("default_data/radar.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO radar (cnpj, tipo_interrup, tempo_max_interrup, pct_max_interrup)
            VALUES (?, ?, ?, ?)
        """,
            (row.cnpj, row.tipo_interrup, row.tempo_max_interrup, row.pct_max_interrup),  # ty: ignore[missing-attribute]
        )

    # enums de sat
    df = pd.read_csv("default_data/sat_tipo.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO sat_tipo (nome)
            VALUES (?)
        """,
            (row.nome,),  # ty: ignore[missing-attribute]
        )

    # sat
    df = pd.read_csv("default_data/sat.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO sat (cnpj, tipo_interrup, tempo_max_interrup, pct_max_interrup)
            VALUES (?, ?, ?, ?)
        """,
            (row.cnpj, row.tipo_interrup, row.tempo_max_interrup, row.pct_max_interrup),  # ty: ignore[missing-attribute]
        )

    # vit
    df = pd.read_csv("default_data/vit.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO vit (cnpj, vel_med, soma_quatro_atrasos, it)
            VALUES (?, ?, ?, ?)
        """,
            (row.cnpj, row.vel_med, row.soma_quatro_atrasos, row.it),  # ty: ignore[missing-attribute]
        )

    # trechos
    df = pd.read_csv("default_data/trechos.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO trechos (id, nome, rodovia, km_inicial, km_final)
            VALUES (?, ?, ?, ?, ?)
        """,
            (row.id, row.nome, row.rodovia, row.km_inicial, row.km_final),  # ty: ignore[missing-attribute]
        )

    # enums de atendimento
    df = pd.read_csv("default_data/atendimento_tipo.csv")
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO atendimento_tipo (nome)
            VALUES (?)
        """,
            (row.nome,),  # ty: ignore[missing-attribute]
        )

    # atendimento
    df = pd.read_csv("default_data/atendimento.csv")
    df["cnpj"] = df["cnpj"].astype(str)
    for row in df.itertuples(index=False):
        cursor.execute(
            """
            INSERT OR IGNORE INTO atendimento (cnpj, rodovia, trecho_id, tipo_servico, tipo_recurso, tipo_parametro, valor)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                row.cnpj,  # ty: ignore[missing-attribute]
                row.rodovia,  # ty: ignore[missing-attribute]
                row.trecho_id,  # ty: ignore[missing-attribute]
                row.tipo_servico,  # ty: ignore[missing-attribute]
                row.tipo_recurso,  # ty: ignore[missing-attribute]
                row.tipo_parametro,  # ty: ignore[missing-attribute]
                row.valor,  # ty: ignore[missing-attribute]
            ),
        )

    conn.commit()
