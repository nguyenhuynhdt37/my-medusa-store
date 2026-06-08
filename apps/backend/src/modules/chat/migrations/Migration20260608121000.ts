import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20260608121000 extends Migration {

  override async up(): Promise<void> {
    this.addSql(`alter table if exists "chat_conversation" drop constraint if exists "chat_conversation_status_check";`);
    this.addSql(`alter table if exists "chat_conversation" alter column "status" set default 'BOT_HANDLED';`);
    this.addSql(`update "chat_conversation" set "status" = case "status" when 'bot' then 'BOT_HANDLED' when 'human' then 'WAITING_ADMIN' when 'closed' then 'CLOSED' else "status" end;`);
    this.addSql(`alter table if exists "chat_conversation" add constraint "chat_conversation_status_check" check ("status" in ('BOT_HANDLED', 'WAITING_ADMIN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'));`);

    this.addSql(`alter table if exists "chat_conversation" add column if not exists "escalation_reason" text null;`);
    this.addSql(`alter table if exists "chat_conversation" add column if not exists "admin_metadata" jsonb null;`);
    this.addSql(`alter table if exists "chat_conversation" add column if not exists "escalated_at" timestamptz null;`);
    this.addSql(`alter table if exists "chat_conversation" add column if not exists "admin_started_at" timestamptz null;`);
    this.addSql(`alter table if exists "chat_conversation" add column if not exists "resolved_at" timestamptz null;`);
    this.addSql(`alter table if exists "chat_conversation" add column if not exists "closed_at" timestamptz null;`);
    this.addSql(`create index if not exists "IDX_chat_conversation_status" on "chat_conversation" ("status") where deleted_at is null;`);
  }

  override async down(): Promise<void> {
    this.addSql(`drop index if exists "IDX_chat_conversation_status";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "closed_at";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "resolved_at";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "admin_started_at";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "escalated_at";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "admin_metadata";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "escalation_reason";`);

    this.addSql(`alter table if exists "chat_conversation" drop constraint if exists "chat_conversation_status_check";`);
    this.addSql(`update "chat_conversation" set "status" = case "status" when 'BOT_HANDLED' then 'bot' when 'WAITING_ADMIN' then 'human' when 'IN_PROGRESS' then 'human' when 'RESOLVED' then 'closed' when 'CLOSED' then 'closed' else "status" end;`);
    this.addSql(`alter table if exists "chat_conversation" add constraint "chat_conversation_status_check" check ("status" in ('bot', 'human', 'closed'));`);
    this.addSql(`alter table if exists "chat_conversation" alter column "status" set default 'bot';`);
  }

}
