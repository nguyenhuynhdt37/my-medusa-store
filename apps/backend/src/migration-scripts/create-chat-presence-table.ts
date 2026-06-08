import { MedusaContainer } from "@medusajs/framework";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";

export default async function create_chat_presence_table({ container }: { container: MedusaContainer }) {
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const pg = container.resolve(ContainerRegistrationKeys.PG_CONNECTION);

  logger.info("Creating chat_presence table if not exists...")

  await pg.raw(`
    CREATE TABLE IF NOT EXISTS chat_presence (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      client_key text,
      user_id text,
      guest_id text,
      user_type text NOT NULL,
      name text,
      online boolean DEFAULT false,
      last_seen_at timestamptz,
      conversation_id text REFERENCES chat_conversation(id) ON DELETE CASCADE,
      created_at timestamptz DEFAULT now(),
      updated_at timestamptz DEFAULT now()
    );
  `)

  // ensure unique constraint on (conversation_id, client_key)
  await pg.raw(`
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE tablename = 'chat_presence' AND indexname = 'uq_chat_presence_conversation_client'
      ) THEN
        CREATE UNIQUE INDEX uq_chat_presence_conversation_client ON chat_presence (conversation_id, client_key);
      END IF;
    END$$;
  `)

  logger.info("chat_presence table ensured")
}
