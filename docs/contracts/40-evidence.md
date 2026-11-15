# قرارداد ۴ — شواهد (Evidence)

نسخه: 0.1 · وابسته به: [00-invariants](00-invariants.md) (I3, I4, I5, I10)

این سند مهم‌ترین سند مجموعه است. اگر شواهد قابل جعل باشند، همهٔ دروازه‌های دیگر بی‌معنا می‌شوند.

**قاعدهٔ بنیادین: عامل شاهد نمی‌سازد.** عامل «ادعا» می‌سازد؛ شاهد را harness ضبط می‌کند.

---

## 1. شاهد چیست

```yaml
evidence_id: ev-00912
kind: test_report            # test_report | exit_code | artifact | metric | scan_report
                             # | env_fingerprint | human_approval
criterion_id: AUTH-001-T1    # به کدام معیار پذیرش مربوط است
producer: harness            # فقط harness؛ هیچ مقدار دیگری پذیرفته نیست
invocation_id: inv-000431    # فراخوانی ابزاری که شاهد را تولید کرد
source_revision: "git:sha..." # دقیقاً چه کدی اجرا شد
env_fingerprint: "sha256:..." # پایتون، سیستم‌عامل، وابستگی‌ها، پروفایل sandbox
sandbox_id: "sbx-..."
captured_at: "..."
content_hash: "sha256:..."    # آدرس محتوا
content_ref: "artifact://..." # خود محتوا در انبار فقط-افزودن
size_bytes: 12034
truncated: false
```

هر شاهد دو ویژگی حیاتی دارد:

- **تولیدکننده‌اش معلوم است** و باید harness باشد.
- **به یک فراخوانی مشخص گره خورده است** — شاهد شناور و بی‌منبع وجود ندارد.

## 2. چه چیزی شاهد نیست

| چیز | وضعیت |
| --- | --- |
| «تست‌ها پاس شدند» در متن مدل | ادعا |
| فایل گزارش که عامل نوشته | ادعا (و در صورت ادعای شاهد بودن: تخلف) |
| تصویر صفحه یا توضیح رفتار | ادعا، مگر با اسکریپت بازتولید |
| نظر مدل دیگر | ارزیابی کمکی، نه شاهد مستقل (I10) |
| خروجی کوتاه‌شده بدون علامت | شاهد معیوب |

## 3. بستهٔ شواهد (Evidence Bundle)

حکم همیشه روی یک بسته صادر می‌شود، نه روی یک شاهد تنها:

```yaml
bundle_id: eb-...
task_id: T-0042
source_revision: "git:sha..."
base_commit: "git:sha..."
policy_hash: "sha256:..."
baseline_hash: "sha256:..."
env_fingerprint: "sha256:..."
items: [ev-00912, ev-00913, ev-00914]
chain_head: "sha256:..."     # زنجیرهٔ hash روی (شاهد قبلی + شاهد فعلی)
```

بسته **فقط-افزودن** است. حذف شاهد از بسته = بستهٔ جدید، و بستهٔ قبلی باطل نمی‌شود، فقط
علامت `superseded` می‌خورد. تاریخ شواهد بازنویسی نمی‌شود.

## 4. محاسبهٔ حکم (fail-closed)

```
برای هر معیار الزامی وظیفه:
  اگر شاهد لازم موجود نیست            → FAIL
  اگر شاهد مربوط به revision دیگری است → FAIL (شاهد کهنه)
  اگر env_fingerprint با محیط فعلی نمی‌خواند → FAIL یا STALE
  اگر producer != harness              → رد شاهد
  اگر criterion از baseline حذف شده    → TAMPER_SUSPECTED
  اگر نوع معیار executable و exit_code != expected → FAIL
  اگر نوع معیار evidence_based و قاعدهٔ خودکار ندارد → REVIEW
  اگر نوع معیار human و approval معتبر نیست → REVIEW
اگر همه PASS: PASS
```

هیچ حالت «نامشخص» وجود ندارد که به نفع وظیفه تفسیر شود. نبود شاهد = شکست.

## 5. کهنگی و drift

شاهد با `(source_revision, env_fingerprint, policy_hash, baseline_hash)` گره خورده است.
تغییر هر یک:

| تغییر | اثر |
| --- | --- |
| کد عوض شد | شاهد کهنه؛ باید بازاجرا شود |
| چکیدهٔ baseline عوض شد | شاهد باطل + نیازمند تأیید انسانی (I5) |
| محیط عوض شد (نسخهٔ پایتون، وابستگی) | شاهد `STALE`؛ Checkpoint نیازمند بازتولید |
| سیاست عوض شد | شاهد معتبر می‌ماند، ولی حکم جدید نیاز به ارزیابی مجدد دارد |

## 6. سناریوهای جعل و تشخیص

| تلاش | تشخیص |
| --- | --- |
| عامل فایل گزارش می‌نویسد | بسته فقط از harness پذیرفته می‌شود؛ فایل بی‌ارجاع نادیده گرفته می‌شود |
| عامل آزمون را ضعیف می‌کند | baseline hash تغییر کرده → `TAMPER_SUSPECTED` |
| عامل خروجی را ویرایش می‌کند | `content_hash` با زنجیره نمی‌خواند |
| شاهد از revision دیگر | `source_revision` تطبیق نمی‌کند |
| اجرا روی درخت آلوده | Verifier روی snapshot تمیز اجرا می‌کند (I10) |

تشخیص در همهٔ این موارد یک نتیجه دارد: **توقف، قرنطینهٔ وظیفه، و گزارش به انسان** — نه تلاش
مجدد.

## 7. شاهد انسانی

تأیید انسان یک شاهد است، اما نه شاهد «صحت فنی»: یعنی «انسان این تصمیم را پذیرفت».
پس هرگز نمی‌تواند جای معیار اجرایی را بگیرد و باید صریحاً در حکم به‌عنوان
`human_approval` ذکر شود تا معلوم باشد کدام بخش با قضاوت انسانی گذشت.

## 8. سؤال‌های باز

- انبار شواهد کجا باشد؟ (پیشنهاد: `.csef/evidence/` در control plane، محتواآدرس، فقط-افزودن.)
- آیا بستهٔ شواهد باید امضای رمزنگاری داشته باشد؟ (پیشنهاد نسخهٔ ۱: نه؛ hash-chain کافی است.
  امضا وقتی لازم می‌شود که چند ماشین/کاربر در میان باشند.)

## 9. رکورد بازبینی (Verification Record)

هر حکم پذیرش به یک رکورد مشخص گره می‌خورد، نه به یک «تست پاس شد»:

```
VERIFICATION RECORD
├── harness_record_id
├── invocation_id
├── task_id
├── source_commit_hash
├── acceptance_bundle_hash
├── policy_version_hash
├── sandbox_image_digest
├── dependency_lock_hash
├── command_spec_hash
├── captured_exit_code
├── captured_stdout_hash
├── captured_stderr_hash
├── execution_status
├── verification_verdict
└── recorded_at
```

مدل: `VerificationRecord` در `src/csef_contracts/evidence.py`.

**هشدار صریح:** این فیلدها به‌تنهایی جعل‌ناپذیری ایجاد نمی‌کنند. محافظت واقعی از رکوردهای
Harness به این‌ها بستگی دارد، نه به schema:

1. **دسترسی نوشتن:** رکورد فقط از فرایند Harness با هویت جداگانه قابل درج است.
2. **ترتیب ثبت:** رکورد پیش از اجرا (`intent`) و پس از اجرا (`outcome`) نوشته می‌شود، در یک
   تراکنش، تا هیچ اجرایی بدون رکورد باقی نماند.
3. **یکپارچگی ذخیره‌سازی:** زنجیرهٔ hash روی رکوردها؛ بازنویسی، تشخیص‌پذیر باشد.
4. **گره‌خوردن به فراخوانی:** رکوردی که به `invocation_id` معتبر وصل نیست، شاهد نیست.

اگر این چهار مورد برقرار نباشند، `VerificationRecord` یک فایل JSON خوش‌فرم است و بس.

### 9.1 اجرای این مدل در کد (پس از بازبینی گام ۵)

پیاده‌سازی v0.2 سه نقص داشت که در بازبینی گام ۵ با کاوش‌های a01–a05 نشان داده شد: حکم از
فراخواننده گرفته می‌شد، شاهد بدون رکورد اجرا پذیرفته می‌شد، و revision/policy به checkpoint
گره نمی‌خورد. اصلاح ([DEC-001](../decisions/DEC-001-authority-boundary.md)):

| لایه | سازوکار |
| --- | --- |
| پیوند شاهد به اجرا | `HarnessJournal` تنها منبع رکورد؛ شاهد بدون رکورد متناظر → `FAIL` |
| تولید حکم | `compute_verdict(task, bundle, inputs, journal)` — حکم پارامتر نیست، خروجی است |
| مجوز | `Controller.verify()` تنها تولیدکنندهٔ `VerificationPermit` و فقط برای `PASS` |
| مصرف مجوز | `promote()` همهٔ گره‌ها را دوباره بررسی می‌کند (commit، bundle، policy، baseline، env) |

**محدودیت باقی‌مانده:** مجوز یک شیء درون‌فرایندی است. کسی که همهٔ hashها را بداند می‌تواند
یکی بسازد؛ تفاوت این است که جعل باید با checkpoint ادعایی سازگار باشد و قابل مشاهده است.
ناممکن‌کردن واقعی، کار مرز I2 (VM/ACL) است.

## 10. محدودیت ذاتی: آزمون سبز یعنی چه

Harness اثبات می‌کند که **یک آزمون معین، با یک دستور معین، روی یک revision معین، در یک محیط
معین، واقعاً اجرا شده و نتیجه‌اش چه بوده است.** اثبات نمی‌کند که آن آزمون تمام نیازمندی تجاری
را پوشش می‌دهد.

این یک محدودیت ذاتی است، نه نقص پیاده‌سازی، و باید صریح در گزارش پوشش نیازمندی دیده شود:

```
requirement_id: AUTH-001
covered_by: [AUTH-001-T1, AUTH-001-T2]
not_covered: ["نرخ قفل‌شدن پس از تلاش ناموفق", "سیاست چرخش رمز"]
coverage_basis: human_approved | inferred
```

گزارش حکمی که پوشش را «کامل» اعلام کند بدون این بخش، ادعایی است که سیستم نمی‌تواند پشتیبانش باشد.

## Step 5 evidence audit — 2026-11-15

EXECUTED counterexamples and test assertion inventory are recorded in
[the audit program](../../verification_step5/PROGRAM.md) and its evidence directory.
Current `compute_verdict` checks metadata presence/freshness but does not join to
`VerificationRecord`, evaluate captured exit codes, authenticate ingestion, look up
invocations, recompute content/baseline bytes, or consistently bind task and item environment.
The label restriction is therefore insufficient to establish I13 authority.

PROPOSED clarification to section 9: write-ahead intent must be durably committed before
the external effect; outcome is committed afterward. The phrase “one transaction” must not
imply atomicity across a database and an arbitrary external effect. Crash reconciliation,
authenticated bundle origin and signed/store-backed verifier authority require an adopted
decision before operational verification can be claimed. See ADR-S5-001 and ADR-S5-003.

## 11. Independent audit addendum — 2026-11-15

EXECUTED: `compute_verdict` can return PASS without a VerificationRecord, captured
exit code or content-byte validation. `promote` accepts a caller-supplied PASS with
an empty bundle. See [audit and counterexamples](70-independent-compatibility.md).
The trust requirements in section 9 describe obligations, not implemented storage
guarantees. Its single-transaction wording needs D9 adjudication: durable intent
must precede an external effect, with outcome committed afterwards; a transaction
left uncommitted across the effect does not satisfy I8.

PROPOSED: D9 binds authoritative verifier results to the exact task, revision,
acceptance, policy, environment, invocation and evidence digest. No enforcement
fix or independent implementation has been certified by this audit.
