import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20260609110000 extends Migration {
  override async up(): Promise<void> {
    this.addSql(`alter table if exists "chat_message" add column if not exists "customer_id" text null;`);
    this.addSql(`alter table if exists "chat_message" add column if not exists "guest_id" text null;`);
    this.addSql(`create index if not exists "IDX_chat_message_customer_id" on "chat_message" ("customer_id") where deleted_at is null;`);
    this.addSql(`create index if not exists "IDX_chat_message_guest_id" on "chat_message" ("guest_id") where deleted_at is null;`);

    this.addSql(`
      update "chat_message" cm
      set
        "customer_id" = coalesce(cm."customer_id", cc."customer_id"),
        "guest_id" = coalesce(cm."guest_id", cc."guest_id")
      from "chat_conversation" cc
      where cm."conversation_id" = cc."id"
        and cm."deleted_at" is null
        and cc."deleted_at" is null
        and (cm."customer_id" is null or cm."guest_id" is null);
    `);
  }

  override async down(): Promise<void> {
    this.addSql(`drop index if exists "IDX_chat_message_guest_id";`);
    this.addSql(`drop index if exists "IDX_chat_message_customer_id";`);
    this.addSql(`alter table if exists "chat_message" drop column if exists "guest_id";`);
    this.addSql(`alter table if exists "chat_message" drop column if exists "customer_id";`);
  }
}
