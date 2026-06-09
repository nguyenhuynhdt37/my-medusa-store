import { retrieveCustomer } from "@lib/data/customer"
import { NextResponse } from "next/server"

export const runtime = "nodejs"

export async function GET() {
  try {
    const customer = await retrieveCustomer()
    return NextResponse.json({ customer })
  } catch (err) {
    console.error("[CUSTOMER_GET_ERROR]", err)
    return NextResponse.json({ customer: null })
  }
}
