---
id: INSECURE-DESERIALIZATION
severity_max: CRITICAL
applies_to: swift
---

# Insecure Deserialization (Swift)

## Intent

Họ `NSCoding`/`NSKeyedUnarchiver` là pickle của Apple platform. API đời cũ — `NSKeyedUnarchiver.unarchiveObject(with:)`, `unarchiveTopLevelObjectWithData`, hoặc unarchiver với `requiresSecureCoding = false` — cho phép data quyết định **class nào được khởi tạo**. Archive độc chế tạo object graph với class bất ngờ → object-substitution attack, từng là gốc của nhiều CVE iOS (ImageIO, Messages).

Vibe coder gặp lỗi compile/deprecation với `NSSecureCoding` thì hay "fix" bằng `requiresSecureCoding = false` — chính là tắt lớp bảo vệ. `JSONDecoder`/`PropertyListDecoder` (Codable) **không** có vấn đề này: type do code chỉ định, data không chọn được class.

Severity phụ thuộc **nguồn archive**: data từ network/AirDrop/file người khác gửi/pasteboard/App Group share với extension = L1 → CRITICAL. Archive do chính app ghi vào sandbox riêng (cache UserDefaults custom object) = thấp hơn nhiều, nhưng vẫn note vì file backup/jailbreak sửa được.

## Khi nào CRITICAL

- `NSKeyedUnarchiver.unarchiveObject(with:)` / `unarchiveTopLevelObjectWithData(_:)` (API insecure-by-design, deprecated) trên data từ:
  - Network response / WebSocket / file download
  - `UIPasteboard` / drag-and-drop / AirDrop / share extension
  - File import (`UIDocumentPicker`, "Open in...")
  - App Group container (extension khác process ghi vào)
- `NSKeyedUnarchiver(forReadingFrom:)` rồi set `unarchiver.requiresSecureCoding = false` với data L1
- `unarchivedObject(ofClass: NSObject.self, from:)` — allowlist rộng đến vô nghĩa

## Khi nào HIGH / MEDIUM (giảm cấp)

- Cùng API cũ nhưng data là file do chính app ghi trong sandbox riêng → MEDIUM (sửa được qua backup/jailbreak; vẫn nên migrate)
- `unarchivedObject(ofClasses:)` với allowlist hẹp nhưng chứa class tự viết có `init(coder:)` làm side effect (ghi file, gọi network) → HIGH, đọc class đó
- Codable (`JSONDecoder`) với type cố định → không flag, kể cả data L1

## Cách reasoning (KHÔNG pattern-match thuần)

1. **Grep** sink: `NSKeyedUnarchiver`, `unarchiveObject`, `unarchiveTopLevelObject`, `requiresSecureCoding`, `NSCoding`.
2. **Read** call site: API nào? Có `ofClasses:` allowlist không? `requiresSecureCoding` bị set `false` ở đâu?
3. **Trace data nguồn**: archive đến từ network/pasteboard/file share (L1) hay file app tự ghi (L3)?
4. **Verify allowlist**: `ofClass:` là type cụ thể (`MyNote.self`) hay `NSObject.self`/`NSArray.self` chung chung? Class trong allowlist có `init(coder:)` custom làm gì?

## Search patterns (Swift-specific)

```
# API deprecated insecure
NSKeyedUnarchiver\.unarchiveObject\(with
unarchiveTopLevelObjectWithData

# Tắt secure coding
requiresSecureCoding\s*=\s*false

# Allowlist quá rộng
unarchivedObject\(ofClass:\s*NSObject\.self
unarchivedObject\(ofClasses:\s*\[NSObject

# Nguồn data đáng ngờ gần unarchive
UIPasteboard|NSPasteboard[\s\S]{0,200}NSKeyedUnarchiver
URLSession[\s\S]{0,300}NSKeyedUnarchiver
```

## Examples

### CRITICAL — flag

```swift
// Unarchive data tải về từ server bằng API deprecated — data chọn class
func handleSyncPayload(_ data: Data) {
    let obj = NSKeyedUnarchiver.unarchiveObject(with: data)   // BAD: L1 + insecure API
    apply(obj as? SyncState)
}
```

```swift
// "Fix" deprecation warning bằng cách tắt secure coding
let unarchiver = try NSKeyedUnarchiver(forReadingFrom: receivedData)  // từ AirDrop
unarchiver.requiresSecureCoding = false                                // BAD
let doc = unarchiver.decodeObject(forKey: NSKeyedArchiveRootObjectKey)
```

```swift
// Allowlist NSObject.self = không allowlist gì cả
let obj = try NSKeyedUnarchiver.unarchivedObject(ofClass: NSObject.self,
                                                 from: pasteboardData)  // BAD
```

### NOT critical — safe

```swift
// Codable — type do code chỉ định, data không chọn được class
let payload = try JSONDecoder().decode(SyncState.self, from: data)
```

```swift
// Secure coding + allowlist hẹp, type cụ thể
let note = try NSKeyedUnarchiver.unarchivedObject(ofClass: Note.self, from: data)

// Collection: liệt kê đúng các class cần
let notes = try NSKeyedUnarchiver.unarchivedObject(
    ofClasses: [NSArray.self, Note.self, NSString.self, NSDate.self],
    from: data)
```

```swift
// Archive app tự ghi/đọc trong sandbox riêng — MEDIUM note, không CRITICAL
let cached = try NSKeyedUnarchiver.unarchivedObject(ofClass: ThemeConfig.self,
                                                    from: localCacheData)
```

## Fix recommendation

1. **Migrate sang Codable** (`JSONDecoder`/`PropertyListDecoder`) cho data mới — loại bỏ cả lớp vấn đề.
2. Bắt buộc NSCoding (interop Objective-C, Core Data transformable) → `unarchivedObject(ofClasses:from:)` với **allowlist hẹp, type cụ thể**; mọi class conform `NSSecureCoding` với `supportsSecureCoding = true`.
3. **Không bao giờ** `requiresSecureCoding = false` cho data ngoài sandbox; gặp lỗi decode thì sửa allowlist, đừng tắt check.
4. Core Data transformable attribute: dùng `NSSecureUnarchiveFromDataTransformer` (default từ iOS 13), không custom transformer tắt secure coding.
5. Data từ pasteboard/share/App Group: validate sau decode (range, độ dài) — secure coding chặn class lạ chứ không chặn giá trị rác.

## Cross-references

- Rule `09-ssrf`: payload từ deep link/share sheet — cùng họ nguồn L1 vào app
- Rule `07-mass-assignment`: decode xong gán nguyên object vào model = cùng kiểu trust data ngoài
- Rule `17-verbose-error-debug-mode`: print lỗi decode kèm raw data ra log
