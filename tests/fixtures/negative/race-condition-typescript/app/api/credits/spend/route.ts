import { NextRequest, NextResponse } from "next/server";
import { db } from "../../../../../src/db";

export async function POST(request: NextRequest) {
  const { userId, amount } = await request.json();

  await db.$transaction(async (tx) => {
    const account = await tx.account.findUnique({ where: { userId } });
    if (!account || account.credits < amount) {
      throw new Error("insufficient credits");
    }

    await tx.account.update({
      where: { userId },
      data: { credits: { decrement: amount } },
    });
  });

  return NextResponse.json({ ok: true });
}
