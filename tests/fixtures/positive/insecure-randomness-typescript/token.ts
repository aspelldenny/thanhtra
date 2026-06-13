// Password-reset token generated from a non-cryptographic PRNG.
export function resetToken(): string {
  return Math.random().toString(36).slice(2) +
         Math.random().toString(36).slice(2);
}
