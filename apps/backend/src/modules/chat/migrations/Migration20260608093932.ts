import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20260608093932 extends Migration {

  override async up(): Promise<void> {
    this.addSql(`create table if not exists "chat_conversation" ("id" text not null, "customer_id" text null, "guest_id" text null, "customer_name" text null, "customer_email" text null, "status" text check ("status" in ('bot', 'human', 'closed')) not null default 'bot', "assigned_admin_id" text null, "last_message_at" timestamptz null, "created_at" timestamptz not null default now(), "updated_at" timestamptz not null default now(), "deleted_at" timestamptz null, constraint "chat_conversation_pkey" primary key ("id"));`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_chat_conversation_deleted_at" ON "chat_conversation" ("deleted_at") WHERE deleted_at IS NULL;`);

    this.addSql(`create table if not exists "chat_message" ("id" text not null, "sender_type" text check ("sender_type" in ('customer', 'guest', 'bot', 'admin')) not null, "sender_id" text null, "content" text not null, "metadata" jsonb null, "conversation_id" text not null, "created_at" timestamptz not null default now(), "updated_at" timestamptz not null default now(), "deleted_at" timestamptz null, constraint "chat_message_pkey" primary key ("id"));`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_chat_message_conversation_id" ON "chat_message" ("conversation_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_chat_message_deleted_at" ON "chat_message" ("deleted_at") WHERE deleted_at IS NULL;`);

    this.addSql(`alter table if exists "chat_message" add constraint "chat_message_conversation_id_foreign" foreign key ("conversation_id") references "chat_conversation" ("id") on update cascade;`);
  }

  override async down(): Promise<void> {
    this.addSql(`alter table if exists "chat_message" drop constraint if exists "chat_message_conversation_id_foreign";`);

    this.addSql(`drop table if exists "chat_conversation" cascade;`);

    this.addSql(`drop table if exists "chat_message" cascade;`);
  }

}
