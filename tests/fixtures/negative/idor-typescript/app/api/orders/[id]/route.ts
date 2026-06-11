import { NextRequest, NextResponse } from "next/server";
import { auth } from "../../../../../src/auth";
import { db } from "../../../../../src/db";

export async function GET(request: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth(request);
  const order = await db.order.findFirst({
    where: { id: params.id, userId: session.user.id },
  });

  return NextResponse.json(order);
}
