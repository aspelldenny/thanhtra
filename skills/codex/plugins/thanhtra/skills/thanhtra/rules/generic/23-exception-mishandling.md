---
id: EXCEPTION-MISHANDLING
severity_max: HIGH
applies_to: all
---

# Exception Mishandling / Fail-Open

## Intent

**Mishandling of Exceptional Conditions** (OWASP Top 10:2025 **A10**, CWE-703/755): code bắt exception rồi **nuốt im** (`except: pass`, empty `catch {}`) hoặc xử lý sai, khiến một **bước kiểm tra bảo mật thất bại nhưng luồng vẫn chạy tiếp như thể đã pass** — đây là **fail-open**.

Nguy hiểm nhất khi exception bị nuốt nằm quanh: verify chữ ký / token, check quyền (authz), xác thực mật khẩu, validate input, kiểm tra license/payment. Khi đó lỗi → bỏ qua check → **bypass bảo mật**.

```python
def is_admin(token):
    try:
        claims = verify_jwt(token)        # ném nếu chữ ký sai / hết hạn
        return claims.get("role") == "admin"
    except Exception:
        pass                              # nuốt lỗi
    return True                           # FAIL-OPEN: verify lỗi → vẫn cho admin
```

Cực kỳ **vibe-code-typical**: AI viết error handling kiểu "cho nó chạy được đã" — bọc `try/except` rộng để hết đỏ, vô tình biến một check thành no-op.

## Khi nào HIGH

- `try/except`/`catch` nuốt lỗi quanh **security check** rồi tiếp tục như đã pass:
  verify chữ ký/JWT/HMAC, check quyền, auth, validate input chống injection.
- Catch nuốt lỗi rồi `return True` / `return user` / `allow` / không re-raise ở
  hàm quyết định cho-phép-hay-không (allow/deny decision).
- Empty catch quanh thao tác **đóng tài nguyên bảo mật**: bỏ qua lỗi khi
  revoke session, xoá token, ghi audit log → hậu quả bảo mật.
- `catch` nuốt rồi tiếp tục dùng biến **chưa được khởi tạo an toàn** (ví dụ
  decrypt fail → vẫn dùng plaintext fallback).

## Khi nào MEDIUM (giảm cấp)

- `except: pass` / empty catch **không** nằm trên đường ra quyết định bảo mật
  (ví dụ nuốt lỗi khi cleanup temp file, parse optional config) — code smell,
  reliability risk, nhưng không trực tiếp bypass bảo mật.
- Catch quá rộng (`except Exception`) có log nhưng vẫn re-raise / vẫn fail
  đúng hướng (fail-closed).

## Khi nào KHÔNG flag

- Catch hẹp, có log, và **fail-closed**: lỗi → từ chối / trả 500 / re-raise.
- `try/finally` chỉ để cleanup, không nuốt và không đổi luồng quyết định.
- Catch một exception cụ thể đã được dự kiến và xử lý đúng nghiệp vụ.

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** tìm handler nuốt lỗi: bare `except:`, `except ...: pass`, empty
   `catch (e) {}`, `.catch(() => {})`, `rescue nil`, `recover()` trống.
2. **Read** ngữ cảnh quanh handler:
   - Bên trong `try` có lệnh **security check** không (verify/authz/validate)?
   - Sau catch, luồng đi tiếp tới đâu? Có `return`/`allow`/dùng biến rủi ro?
3. **Xác định hướng fail**: lỗi xảy ra → kết cục là **deny (closed)** hay
   **allow (open)**? Chỉ fail-open quanh security mới là HIGH.
4. **Phân biệt** swallow-vô-hại (cleanup, optional) với swallow-nguy-hiểm
   (quyết định cho phép). Không phải mọi `except: pass` đều là lỗ hổng.

## Search patterns (gợi ý — KHÔNG chạy literal, dùng Grep tool)

### Python

```
except\s*:\s*$            # bare except
except\s*:\s*pass
except\s+\w+\s*:\s*pass
except\s+Exception\s*:\s*pass
contextlib\.suppress\s*\(
```

### JavaScript / TypeScript

```
catch\s*\([^)]*\)\s*\{\s*\}          # empty catch
catch\s*\{\s*\}                       # optional-catch-binding empty
\.catch\s*\(\s*\(\s*\)\s*=>\s*\{?\s*\}?\s*\)   # swallowed promise rejection
catch\s*\([^)]*\)\s*\{\s*//
```

### Go

```
if\s+err\s*!=\s*nil\s*\{\s*\}         # checked rồi bỏ trống
_\s*=\s*\w+\(\)                        # gán lỗi vào _
recover\s*\(\s*\)
```

### Java / Kotlin / C#

```
catch\s*\([^)]*\)\s*\{\s*\}
catch\s*\([^)]*\)\s*\{\s*//
catch\s*\(Exception\s+\w+\)\s*\{\s*\}
```

### PHP / Ruby

```
catch\s*\(\\?Throwable[^)]*\)\s*\{\s*\}
rescue\s*=>\s*\w*\s*$
rescue\s+nil
@\w+\(                                 # PHP error-suppression operator
```

## Examples

### HIGH — flag

```javascript
// Express — verify chữ ký webhook thất bại vẫn xử lý payload
function handleWebhook(req, res) {
  try {
    verifySignature(req.headers['x-sig'], req.body);  // ném nếu sai
  } catch (e) {
    // bỏ qua — "để webhook không bị fail"
  }
  processPayment(req.body);              // FAIL-OPEN: payload giả vẫn được xử lý
  res.json({ ok: true });
}
```

```python
# Decrypt fail nhưng fallback dùng plaintext
def read_secret(blob):
    try:
        return decrypt(blob, KEY)
    except Exception:
        return blob          # FAIL-OPEN: trả nguyên ciphertext/plaintext chưa giải mã
```

```go
// Go — bỏ qua lỗi xác thực
claims, err := jwt.Verify(token)
if err != nil {
    // ignore
}
if claims.Role == "admin" {   // claims có thể nil/zero → panic hoặc bypass
    grantAdmin()
}
```

```python
# Bare except nuốt cả check authz
def can_access(user, doc):
    try:
        if not user.is_owner(doc):
            raise PermissionError()
    except Exception:
        pass
    return True               # FAIL-OPEN: PermissionError bị nuốt → luôn cho phép
```

### NOT critical — không flag

```python
# Fail-closed: lỗi verify → từ chối
def is_admin(token):
    try:
        claims = verify_jwt(token)
    except InvalidTokenError:
        logger.warning("token verify failed")
        return False          # fail-closed
    return claims.get("role") == "admin"
```

```javascript
// Catch chỉ quanh cleanup, không đổi quyết định bảo mật
try {
  fs.unlinkSync(tmpPath);     // best-effort xoá temp
} catch (e) {
  logger.debug('temp cleanup skipped', e);
}
```

```python
# Swallow optional config — không liên quan bảo mật
try:
    timeout = int(cfg["timeout"])
except (KeyError, ValueError):
    timeout = 30              # default hợp lý, không phải security decision
```

## Fix recommendation

1. **Fail-closed mặc định**: trên đường ra quyết định cho-phép, lỗi phải dẫn
   tới **deny**, không phải allow.
   ```python
   try:
       claims = verify_jwt(token)
   except InvalidTokenError:
       return False            # KHÔNG return True / pass
   ```
2. **Bắt exception hẹp** đúng loại dự kiến, để lỗi bất ngờ nổi lên (re-raise),
   không nuốt bằng `except Exception`/`catch (e) {}`.
3. **Log + re-raise** thay vì nuốt im: nếu không xử lý được, để nó fail thật.
   ```javascript
   } catch (e) { logger.error(e); throw e; }
   ```
4. **Không fallback sang trạng thái kém an toàn** (plaintext khi decrypt fail,
   `allow` khi authz lỗi). Fallback phải an toàn hơn hoặc bằng.
5. **Tách cleanup khỏi quyết định**: dùng `finally` cho cleanup; đừng để
   `catch` cleanup vô tình nuốt lỗi của bước bảo mật phía trước.
6. **Audit grep**: tìm `except: pass`, empty `catch {}`, `if err != nil {}` —
   với mỗi cái, hỏi "nếu lỗi xảy ra, luồng có đi tiếp như đã pass không?".

## Cross-references

- Cross-check với `12-broken-access-control`: fail-open quanh authz chính là
  một biến thể của broken access control.
- Cross-check với `14-jwt-none-algorithm`: nuốt lỗi verify JWT = chấp nhận
  token không hợp lệ, cùng hậu quả với none-alg.
- Cross-check với `17-verbose-error-debug-mode`: hai mặt của cùng vấn đề xử lý
  lỗi — một bên lộ quá nhiều, một bên nuốt quá nhiều.
