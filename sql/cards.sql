CREATE TABLE IF NOT EXISTS cards (
    id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    multiverseid BIGINT NULL,
    name TEXT NOT NULL,
    card_text MEDIUMTEXT NOT NULL,
    artist TEXT NOT NULL,
    set_code VARCHAR(32) NOT NULL,
    image_url TEXT NULL,
    source_json MEDIUMTEXT NULL,
    details_json MEDIUMTEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
