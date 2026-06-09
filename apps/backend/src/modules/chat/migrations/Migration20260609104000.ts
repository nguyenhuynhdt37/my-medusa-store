import { Migration } from "@mikro-orm/migrations"

export class Migration20260609104000 extends Migration {
  async up(): Promise<void> {
    this.addSql(`alter table if exists "chat_presence" alter column "id" type text using "id"::text;`)
  }

  async down(): Promise<void> {
    this.addSql(`alter table if exists "chat_presence" alter column "id" type uuid using "id"::uuid;`)
  }
}
