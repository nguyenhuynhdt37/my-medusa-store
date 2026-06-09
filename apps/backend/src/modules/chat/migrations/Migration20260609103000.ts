import { Migration } from "@mikro-orm/migrations"

export class Migration20260609103000 extends Migration {
  async up(): Promise<void> {
    this.addSql(`alter table if exists "chat_presence" add column if not exists "created_at" timestamptz not null default now();`)
    this.addSql(`alter table if exists "chat_presence" add column if not exists "updated_at" timestamptz not null default now();`)
    this.addSql(`alter table if exists "chat_presence" add column if not exists "deleted_at" timestamptz null;`)
    this.addSql(`create index if not exists "IDX_chat_presence_deleted_at" on "chat_presence" ("deleted_at") where deleted_at is not null;`)
  }

  async down(): Promise<void> {
    this.addSql(`drop index if exists "IDX_chat_presence_deleted_at";`)
    this.addSql(`alter table if exists "chat_presence" drop column if exists "deleted_at";`)
    this.addSql(`alter table if exists "chat_presence" drop column if exists "updated_at";`)
    this.addSql(`alter table if exists "chat_presence" drop column if exists "created_at";`)
  }
}
