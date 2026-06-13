---
id: INSECURE-RANDOMNESS
severity_max: HIGH
applies_to: all
---

# Insecure Randomness for Security Values

## Intent

Dùng **PRNG không mật mã** (`Math.random()`, `random.random()`, `rand()`,
`mt_rand()`) để sinh giá trị bảo mật — token, OTP, session ID, password-reset
token, CSRF token, API key, salt, mã mời. Các PRNG này **predictable**: state
nhỏ, seed đoán được (thường theo thời gian), output có thể bị tái dựng → kẻ tấn
công đoán/brute-force được giá trị đáng lẽ phải bí mật.

```javascript
// Token reset mật khẩu sinh từ Math.random — đoán được
const token = Math.random().toString(36).slice(2);
// Math.random dùng xorshift128+, không phải CSPRNG → brute-force / dự đoán
```

CWE-330 (Use of Insufficiently Random Values), nằm dưới OWASP A04 (Insecure
Design) / A02 (Cryptographic Failures). **Vibe-code-typical**: AI sinh
`Math.random()` cho token vì đó là hàm random "ai cũng biết", trong khi CSPRNG
cần import riêng.

## Khi nào HIGH

- PRNG không mật mã sinh giá trị **xác thực/bí mật**: session ID, auth token,
  password-reset / email-verify token, OTP/2FA code, CSRF token, API key,
  giá trị "secret link" / mã mời dùng để cấp quyền.
- Seed cố định hoặc theo thời gian (`srand(time(0))`, `random.seed(timestamp)`)
  cho giá trị bảo mật.
- Tự "ghép" token từ `Math.random()` nhiều lần / `Date.now()` + counter.

## Khi nào MEDIUM (giảm cấp)

- PRNG không mật mã cho giá trị **bán nhạy cảm**: filename tạm, jitter retry,
  cache-buster, ID không dùng để cấp quyền nhưng nếu đoán được vẫn gây phiền
  (ví dụ trùng/đụng).
- Salt sinh bằng PRNG yếu nhưng dùng kèm hashing mạnh (giảm tác động).

## Khi nào KHÔNG flag

- CSPRNG đúng: `secrets` (Python), `crypto.randomBytes`/`crypto.randomUUID`
  (Node), `crypto/rand` (Go), `random_bytes`/`random_int` (PHP),
  `SecureRandom` (Java/Ruby), `SystemRandom`, `getrandom(2)`, `/dev/urandom`.
- PRNG yếu cho mục đích **không bảo mật**: animation, sampling thống kê, shuffle
  hiển thị, dữ liệu test/seed, game phi cạnh tranh.
- UUIDv4 từ thư viện chuẩn (đã dùng CSPRNG bên dưới).

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** tìm PRNG yếu: `Math.random`, `random.` (Python `random` module),
   `rand(`, `mt_rand(`, `srand(`, `Random()` (Java util), `rand::random`.
2. **Trace giá trị**: output của random đó **dùng làm gì**? Đi vào token /
   header `Set-Cookie` / cột `session_id` / email reset / so sánh OTP?
   → bảo mật → HIGH. Đi vào UI/sampling → không flag.
3. **Phân biệt module**: Python `random` (yếu) vs `secrets`/`SystemRandom`
   (an toàn). Node `Math.random` (yếu) vs `crypto.*` (an toàn). Đừng flag nhầm
   CSPRNG.
4. **Kiểm tra seed**: có `seed(...)` theo thời gian/cố định không → càng dễ đoán.

## Search patterns (gợi ý — KHÔNG chạy literal, dùng Grep tool)

### JavaScript / TypeScript

```
Math\.random\s*\(
new\s+Date\(\)\.getTime\(\).*token
Date\.now\(\).*(token|otp|id)
```
An toàn (KHÔNG flag): `crypto\.randomBytes`, `crypto\.randomUUID`,
`crypto\.getRandomValues`.

### Python

```
random\.(random|randint|randrange|choice|choices|sample|getrandbits|shuffle)\s*\(
random\.seed\s*\(
```
An toàn: `secrets\.`, `SystemRandom\(`, `os\.urandom`.

### PHP

```
\bmt_rand\s*\(|\brand\s*\(|\buniqid\s*\(|\bmt_srand\s*\(|\bsrand\s*\(
```
An toàn: `random_bytes`, `random_int`, `bin2hex(random_bytes(`.

### Go / Java / Ruby / C / Rust

```
math/rand                              # Go: dùng cho token là sai
\bnew\s+Random\s*\(                     # Java java.util.Random
\brand\s*\(\s*\)|srand\s*\(             # C
\brand::random|thread_rng\(\)          # Rust (yếu cho crypto)
\bSecureRandom\b                        # Java/Ruby — đây là AN TOÀN, đừng flag
```

## Examples

### HIGH — flag

```javascript
// Node — session token từ Math.random
function newSessionId() {
  return Math.random().toString(36).slice(2) +
         Math.random().toString(36).slice(2);   // đoán được state PRNG
}
```

```python
# Python — OTP 6 số từ random module
import random
def gen_otp():
    return f"{random.randint(0, 999999):06d}"   # predictable, brute-force OTP
```

```php
// PHP — token reset mật khẩu
$token = md5(mt_rand());                          // mt_rand seed-able → đoán token
mail($user, "Reset: /reset?token=$token");
```

```go
// Go — API key từ math/rand
import "math/rand"
func apiKey() string {
    b := make([]byte, 32)
    for i := range b { b[i] = byte(rand.Intn(256)) }  // không phải crypto/rand
    return hex.EncodeToString(b)
}
```

### NOT critical — không flag

```javascript
// CSPRNG đúng cho token
import { randomBytes, randomUUID } from 'crypto';
const token = randomBytes(32).toString('hex');
const id = randomUUID();
```

```python
# secrets cho token, OTP
import secrets
token = secrets.token_urlsafe(32)
otp = f"{secrets.randbelow(1000000):06d}"
```

```javascript
// Math.random cho mục đích phi bảo mật — OK
const jitter = Math.random() * 100;        // retry backoff jitter
const pick = items[Math.floor(Math.random() * items.length)];  // UI shuffle
```

## Fix recommendation

1. **Dùng CSPRNG cho mọi giá trị bảo mật:**
   ```javascript
   import { randomBytes } from 'crypto';
   const token = randomBytes(32).toString('hex');   // 256-bit, không đoán được
   ```
   ```python
   import secrets
   token = secrets.token_urlsafe(32)
   otp = f"{secrets.randbelow(10**6):06d}"
   ```
   ```php
   $token = bin2hex(random_bytes(32));
   $code  = random_int(0, 999999);
   ```
   ```go
   import "crypto/rand"
   b := make([]byte, 32); rand.Read(b)
   ```
2. **Đủ entropy**: token ≥ 128-bit (16 byte), tốt hơn 256-bit. OTP ngắn phải đi
   kèm rate-limit + hết hạn (cross-check `18-missing-rate-limit`).
3. **UUID**: dùng `crypto.randomUUID()` / `uuid4` từ thư viện chuẩn, không tự
   ghép từ `Date.now()` + `Math.random()`.
4. **Không seed cố định/theo thời gian** cho bất kỳ giá trị bảo mật nào.
5. **Lint rule**: cấm `Math.random`/`random.*`/`mt_rand` trong module xử lý
   auth/token (ESLint `sonarjs/pseudo-random`, Bandit `B311`, gosec `G404`).

## Cross-references

- Cross-check với `13-weak-password-hashing`: cả hai là lỗi cryptographic
  primitives — chọn sai công cụ cho dữ liệu nhạy cảm.
- Cross-check với `06-brute-force` và `18-missing-rate-limit`: OTP/token yếu
  entropy + thiếu rate-limit = đoán được trong thực tế.
- Cross-check với `01-hardcoded-secret`: token sinh sai cách cũng nguy hiểm như
  secret lộ — đều là khủng hoảng về giá trị bí mật.
