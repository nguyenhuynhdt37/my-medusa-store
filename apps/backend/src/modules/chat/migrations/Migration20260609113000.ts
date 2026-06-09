import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20260609113000 extends Migration {
  override async up(): Promise<void> {
    this.addSql(`alter table if exists "chat_conversation" add column if not exists "channel" text not null default 'WEB';`);
    this.addSql(`alter table if exists "chat_conversation" add column if not exists "external_user_id" text null;`);
    this.addSql(`alter table if exists "chat_message" add column if not exists "channel" text not null default 'WEB';`);
    this.addSql(`alter table if exists "chat_message" add column if not exists "external_message_id" text null;`);
    this.addSql(`create index if not exists "IDX_chat_conversation_channel_external_user_id" on "chat_conversation" ("channel", "external_user_id") where deleted_at is null;`);
    this.addSql(`create index if not exists "IDX_chat_message_channel" on "chat_message" ("channel") where deleted_at is null;`);
  }

  override async down(): Promise<void> {
    this.addSql(`drop index if exists "IDX_chat_message_channel";`);
    this.addSql(`drop index if exists "IDX_chat_conversation_channel_external_user_id";`);
    this.addSql(`alter table if exists "chat_message" drop column if exists "external_message_id";`);
    this.addSql(`alter table if exists "chat_message" drop column if exists "channel";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "external_user_id";`);
    this.addSql(`alter table if exists "chat_conversation" drop column if exists "channel";`);
  }
}
