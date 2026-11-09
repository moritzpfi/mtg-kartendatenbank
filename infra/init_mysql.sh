#!/usr/bin/env bash
(
set -euo pipefail
MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot <<'SQL'
CREATE DATABASE IF NOT EXISTS mtg_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON mtg_test.* TO 'mtg'@'%';
SQL
)
