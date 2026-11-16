CREATE TABLE IF NOT EXISTS concessionaria (
    cnpj VARCHAR(14) PRIMARY KEY,
    no_fantasia VARCHAR(1024) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS pedagio_tipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS pedagio (
    cnpj VARCHAR(14) NOT NULL PRIMARY KEY,
    tipo_interrup INTEGER NOT NULL,
    tempo_max_interrup INTEGER NOT NULL,
    FOREIGN KEY (cnpj) REFERENCES concessionaria(cnpj),
    FOREIGN KEY (tipo_interrup) REFERENCES pedagio_tipo(id)
);

CREATE TABLE IF NOT EXISTS radar_tipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS radar (
    cnpj VARCHAR(14) NOT NULL PRIMARY KEY,
    tipo_interrup INTEGER NOT NULL,
    tempo_max_interrup INTEGER,
    pct_max_interrup  FLOAT,
    FOREIGN KEY (cnpj) REFERENCES concessionaria(cnpj),
    FOREIGN KEY (tipo_interrup) REFERENCES radar_tipo(id)
);

CREATE TABLE IF NOT EXISTS sat_tipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS sat (
    cnpj VARCHAR(14) NOT NULL PRIMARY KEY,
    tipo_interrup INTEGER NOT NULL,
    tempo_max_interrup INTEGER,
    pct_max_interrup  FLOAT,
    FOREIGN KEY (cnpj) REFERENCES concessionaria(cnpj),
    FOREIGN KEY (tipo_interrup) REFERENCES sat_tipo(id)
);

CREATE TABLE IF NOT EXISTS vit (
    cnpj VARCHAR(14) NOT NULL PRIMARY KEY,
    vel_med FLOAT,
    soma_quatro_atrasos INTEGER,
    it INTEGER, -- intervalo de tempo entre 2 passagens por um mesmo ponto
    FOREIGN KEY (cnpj) REFERENCES concessionaria(cnpj)
);

CREATE TABLE IF NOT EXISTS atendimento_tipo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS trechos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    rodovia INTEGER NOT NULL,
    km_inicial DOUBLE NOT NULL,
    km_final DOUBLE NOT NULL,
    CHECK (km_inicial < km_final)
);

CREATE TABLE IF NOT EXISTS atendimento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj VARCHAR(14) NOT NULL,
    rodovia INTEGER,
    trecho_id INTEGER,
    tipo_servico TEXT NOT NULL,
    tipo_recurso TEXT NOT NULL,
    tipo_parametro INTEGER NOT NULL,
    valor DOUBLE NOT NULL,
    FOREIGN KEY (tipo_parametro) REFERENCES atendimento_tipo(id),
    UNIQUE (cnpj, rodovia, trecho_id, tipo_servico, tipo_recurso, tipo_parametro)
);