import { NextRequest, NextResponse } from "next/server";
import { db } from "../../../../../src/db";

export async function GET(_request: NextRequest, { params }: { params: { id: string } }) {
  const order = await db.order.findUnique({ where: { id: params.id } });
  return NextResponse.json(order);
}
