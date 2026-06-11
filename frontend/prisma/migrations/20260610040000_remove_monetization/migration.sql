-- Remove monetization/billing and email-notification artifacts.
DROP TABLE IF EXISTS "stripe_webhook_events";

ALTER TABLE "users" DROP COLUMN IF EXISTS "plan";
ALTER TABLE "users" DROP COLUMN IF EXISTS "subscription_status";
ALTER TABLE "users" DROP COLUMN IF EXISTS "stripe_customer_id";
ALTER TABLE "users" DROP COLUMN IF EXISTS "stripe_subscription_id";
ALTER TABLE "users" DROP COLUMN IF EXISTS "billing_period_start";
ALTER TABLE "users" DROP COLUMN IF EXISTS "billing_period_end";
ALTER TABLE "users" DROP COLUMN IF EXISTS "trial_ends_at";
ALTER TABLE "users" DROP COLUMN IF EXISTS "notify_on_completion";

ALTER TABLE "tasks" DROP COLUMN IF EXISTS "completion_notification_sent_at";

-- Per-user default model selection
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_llm_model" VARCHAR(200);

