PRAGMA foreign_keys = ON;

-- Bank statement files found under data/inputs
CREATE TABLE IF NOT EXISTS ficheros (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario          TEXT NOT NULL,
    ruta             TEXT NOT NULL,                 -- relative to rutas.inputs
    sha256           TEXT NOT NULL UNIQUE,
    formato          TEXT NOT NULL,                 -- csv | tsv | desconocido
    firma_cabecera   TEXT,
    estado           TEXT NOT NULL DEFAULT 'pendiente'
                     CHECK (estado IN ('pendiente','en_proceso','procesado','error','pendiente_confirmacion')),
    n_operaciones    INTEGER,
    detectado_en     TEXT NOT NULL,                 -- ISO 8601
    procesado_en     TEXT,
    error            TEXT
);

-- Column mappings keyed by header signature (one per bank format)
CREATE TABLE IF NOT EXISTS formatos_extracto (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    firma_cabecera   TEXT NOT NULL UNIQUE,
    mapeo_json       TEXT NOT NULL,                 -- serialised FormatoExtracto
    confirmado       INTEGER NOT NULL DEFAULT 0,    -- 0/1
    propuesto_con    TEXT,                          -- model that proposed it
    creado_en        TEXT NOT NULL
);

-- Household accounts (synced from settings.yaml)
CREATE TABLE IF NOT EXISTS cuentas (
    iban             TEXT PRIMARY KEY,              -- normalised: upper case, no spaces
    usuario          TEXT NOT NULL,
    alias            TEXT
);

-- Closed list of categories (synced from settings.yaml)
CREATE TABLE IF NOT EXISTS categorias (
    nombre           TEXT PRIMARY KEY,
    descripcion      TEXT NOT NULL,
    activa           INTEGER NOT NULL DEFAULT 1
);

-- Bank operations
CREATE TABLE IF NOT EXISTS operaciones (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    fichero_id                 INTEGER NOT NULL REFERENCES ficheros(id),
    usuario                    TEXT NOT NULL,
    cuenta_iban                TEXT,                -- TODO(P2): may stay NULL until resolved
    fecha                      TEXT NOT NULL,       -- YYYY-MM-DD (operation date)
    fecha_valor                TEXT,
    importe_centimos           INTEGER NOT NULL,    -- signed: negative = debit
    saldo_posterior_centimos   INTEGER,
    moneda                     TEXT NOT NULL DEFAULT 'EUR',
    concepto_original          TEXT NOT NULL,
    iban_contraparte           TEXT,                -- TODO(P2)
    hash_operacion             TEXT NOT NULL UNIQUE,
    tipo_transferencia         TEXT NOT NULL DEFAULT 'ninguna'
                               CHECK (tipo_transferencia IN ('ninguna','interna_propia','entre_personas')),
    -- Enrichment (S1.2)
    concepto_limpio            TEXT,
    categoria                  TEXT REFERENCES categorias(nombre),
    etiqueta_libre             TEXT,                -- normalised: lower case, no accents
    enriquecida_en             TEXT,
    enriquecida_con            TEXT,                -- "<modelo>|<version_prompt>"
    intentos_enriquecimiento   INTEGER NOT NULL DEFAULT 0,
    creada_en                  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_operaciones_fecha       ON operaciones(fecha);
CREATE INDEX IF NOT EXISTS idx_operaciones_usuario     ON operaciones(usuario, fecha);
CREATE INDEX IF NOT EXISTS idx_operaciones_enriquecida ON operaciones(enriquecida_en);

-- Summaries produced by the analysis
CREATE TABLE IF NOT EXISTS resumenes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo             TEXT NOT NULL CHECK (tipo IN ('semana','mes')),
    periodo          TEXT NOT NULL,                 -- '2026-W46' or '2026-11'
    ambito           TEXT NOT NULL,                 -- 'hogar' or a user name
    estado           TEXT NOT NULL DEFAULT 'vigente' CHECK (estado IN ('vigente','obsoleto')),
    contenido_md     TEXT NOT NULL,
    metricas_json    TEXT NOT NULL,
    generado_en      TEXT NOT NULL,
    generado_con     TEXT,
    UNIQUE (tipo, periodo, ambito)
);
