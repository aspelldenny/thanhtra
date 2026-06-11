import type { NextApiRequest, NextApiResponse } from "next";
import { sequelize } from "../../../src/db";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const email = String(req.query.email || "");
  const rows = await sequelize.query(`SELECT * FROM users WHERE email = '${email}'`);
  res.status(200).json(rows);
}
