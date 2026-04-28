-- 002_subcategories.sql
-- One-level subcategory support. Adds a nullable parent_id pointing back
-- at categories(id). Existing rows stay valid (parent_id = NULL = top-level).
-- ON DELETE behaviour is enforced manually in CategoryRepository.delete()
-- so it works regardless of SQLite's handling of FK actions on
-- ALTER-TABLE-added columns.

ALTER TABLE categories ADD COLUMN parent_id INTEGER REFERENCES categories(id);
CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
