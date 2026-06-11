import { NextRequest, NextResponse } from "next/server";
import { db } from "../../../../../src/db";

export async function POST(request: NextRequest) {
  const { userId, amount } = await request.json();
  const account = await db.account.findUnique({ where: { userId } });

  if (!account || account.credits < amount) {
    return NextResponse.json({ error: "insufficient credits" }, { status: 400 });
  }

  await db.account.update({
    where: { userId },
    data: { credits: account.credits - amount },
  });

  return NextResponse.json({ ok: true });
}
