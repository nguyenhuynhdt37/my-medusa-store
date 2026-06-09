import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20260608220000 extends Migration {

  override async up(): Promise<void> {
    this.addSql(`create index if not exists "IDX_chat_conversation_customer_id" on "chat_conversation" ("customer_id") where deleted_at is null;`);
    this.addSql(`create index if not exists "IDX_chat_conversation_guest_id" on "chat_conversation" ("guest_id") where deleted_at is null;`);
  }

  override async down(): Promise<void> {
    this.addSql(`drop index if exists "IDX_chat_conversation_customer_id";`);
    this.addSql(`drop index if exists "IDX_chat_conversation_guest_id";`);
  }

}
