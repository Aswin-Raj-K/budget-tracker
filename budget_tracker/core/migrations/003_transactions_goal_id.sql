-- 003_transactions_goal_id.sql
-- Link transfer transactions to the goal that produced them so the
-- Goals tab can show "transactions for this goal". Nullable — most
-- transactions aren't goal-related. ON DELETE behaviour is enforced
-- in GoalRepository.delete() (NULLs the column on linked rows before
-- the parent goes away) for the same reasons we did this manually
-- on categories.parent_id in 002.

ALTER TABLE transactions ADD COLUMN goal_id INTEGER REFERENCES goals(id);
CREATE INDEX IF NOT EXISTS idx_tx_goal ON transactions(goal_id);
