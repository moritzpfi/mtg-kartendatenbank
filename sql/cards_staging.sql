CREATE TABLE IF NOT EXISTS cards_staging (
    id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    subtypes TEXT NOT NULL,
    card_text MEDIUMTEXT NOT NULL,
    flavor MEDIUMTEXT NOT NULL,
    artist TEXT NOT NULL,
    image_url TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
