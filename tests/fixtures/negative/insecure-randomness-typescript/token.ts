import { randomBytes } from "crypto";

// CSPRNG-backed token — 256 bits of entropy.
export function resetToken(): string {
  return randomBytes(32).toString("hex");
}
