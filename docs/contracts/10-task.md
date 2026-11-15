# قرارداد ۱ — وظیفه (Task)

نسخه: 0.1 · وابسته به: [00-invariants](00-invariants.md) (I2, I4, I5, I12)

وظیفه کوچک‌ترین واحدی است که می‌تواند وارد وضعیت معتبر شود یا نشود. وظیفه **نه** یک پیام به مدل
است و **نه** یک واحد چت؛ یک پروندهٔ مهندسی با ورودی، بودجه، شرط پایان و شواهد است.

---

## 1. پروندهٔ وظیفه

```yaml
task_id: T-0042
requirement_ids: [AUTH-001]        # حداقل یک نیازمندی؛ بدون آن وظیفه بی‌معناست
profile: standard                  # quick | standard | advanced
objective: "ورود با اطلاعات معتبر کار کند و ورود نامعتبر رد شود"
frozen_acceptance_ref:
  baseline_hash: "sha256:..."      # مرجع به baseline در control plane، نه کپی
  criteria: [AUTH-001-T1, AUTH-001-T2]
scope:
  writable_paths: ["src/auth/**", "tests/**"]
  readonly_paths: ["src/core/**"]
  max_files_changed: 8
  max_lines_changed: 400
budgets:
  max_patch_attempts: 3
  max_cost_usd: 2.50
  max_wall_clock_s: 1800
  max_tool_calls: 120
inputs:
  context_receipt: "ctx-..."       # دقیقاً چه چیزی به مدل داده شد
  open_decisions: []               # تصمیم‌های باز که باید توسط انسان حل شوند
deliverables: ["source_diff", "test_report", "notes"]
```

قاعده: هر وظیفه یا به `requirement_id` گره خورده یا دور انداخته می‌شود. وظیفهٔ یتیم مجاز نیست؛
کار بدون نیازمندی، هدر بودجه است.

## 2. حالت‌ها

```
CREATED
  → PLANNED
  → PREPARED
  → AUTHORIZED
  → EXECUTING
  → COLLECTING
  → VERIFYING
      ├─ PASS      → CHECKPOINTING → DONE
      ├─ FAIL      → DIAGNOSING → PATCHING → VERIFYING (محدود)
      ├─ REVIEW    → AWAITING_HUMAN
      ├─ BLOCKED   → AWAITING_HUMAN   (شامل BLOCKED_ON_AMBIGUITY)
      └─ ABANDONED
```

`FAILED`/`ABANDONED`/`DONE` پایانی‌اند. هیچ گذار معکوسی وجود ندارد؛ یک تلاش جدید = پروندهٔ
تلاش جدید با `parent_attempt_id`، نه بازگشت وضعیت.

## 3. گذارها و شرط‌های نگهبان

| گذار | شرط نگهبان | اگر برقرار نباشد |
| --- | --- | --- |
| CREATED → PLANNED | معیارهای پذیرش قطعی موجود و hash-قفل‌شده (I5) | توقف: `MISSING_ACCEPTANCE` |
| PLANNED → PREPARED | worktree ساخته، lease گرفته (I9)، اثر انگشت محیط ثبت | توقف: `PREPARE_FAILED` |
| PREPARED → AUTHORIZED | برای هر capability لازم، تصمیم سیاست معلوم است؛ بودجه‌ها عددی‌اند (I6) | `deny` → `POLICY_DENIED`؛ `ask` → AWAITING_HUMAN |
| AUTHORIZED → EXECUTING | `open_decisions` خالی است (I12) | توقف: `BLOCKED_ON_AMBIGUITY` |
| EXECUTING → COLLECTING | عامل اعلام پایان، یا بودجه/زمان تمام شد | — |
| COLLECTING → VERIFYING | همهٔ شواهد الزامی جمع شده‌اند | شاهد ناقص = `FAIL` (I6) |
| VERIFYING → PASS | همهٔ معیارهای قطعی PASS و بدون `REVIEW` معلق | — |
| PASS → CHECKPOINTING | مجوز Verifier معتبر است (I4) | توقف: `VERDICT_FORGERY_SUSPECTED` |

نکته: `COLLECTING` یک مرحلهٔ واقعی است نه تشریفات. اگر شواهد الزامی جمع نشوند، وظیفه **شکست
خورده** است، حتی اگر کد درست به نظر برسد.

## 4. سه نوع معیار و معنای دقیق «تمام»

| نوع | سازندهٔ حکم | اثر روی checkpoint |
| --- | --- | --- |
| `executable` | harness (اجرای آزمون) | مانع: تا PASS نشود checkpoint ساخته نمی‌شود |
| `evidence_based` | جدول قواعد روی شواهد ماشینی؛ در غیر این صورت انسان | اگر خودکار PASS نشود → `REVIEW` (مانع) |
| `human` | انسان | `APPROVED` لازم؛ در غیر این صورت `REVIEW` |

**تمام شدگی = همهٔ معیارهای الزامی حکم مثبت دارند.** هیچ درصدی، هیچ «به‌قدر کافی خوب».
یک معیار `human` معلق، وظیفه را در `AWAITING_HUMAN` نگه می‌دارد؛ checkpoint نمی‌سازد.

برای اینکه استقلال با معطلی انسانی کشته نشود: تأییدهای انسانی **دسته‌ای** در مرزهای گیت
جمع‌آوری می‌شوند، نه به‌ازای هر گام. یک صف بازبینی، نه یک مودال مزاحم.

## 5. بودجهٔ تلاش اصلاح

- `max_patch_attempts` به‌ازای وظیفه، نه به‌ازای خطا.
- هر تلاش باید artifact تشخیص (`diagnosis`) داشته باشد که ریشهٔ خطا را متفاوت از تلاش قبلی
  توضیح دهد؛ تلاش بدون تشخیص جدید مجاز نیست.
- اثر انگشت شکست تکراری = `normalized_error_signature + failing_criterion_id`. تکرار همان اثر
  انگشت دو بار → تلاش سوم ممنوع؛ نیازمند طرح جدید یا انسان.
- تلاش‌ها هم از بودجهٔ پول و هم از بودجهٔ تعداد مصرف می‌کنند; هر کدام اول تمام شد، توقف.
- دست‌کاری آزمون پذیرش (تلاش برای تغییر baseline) نتیجه‌اش `TAMPER_SUSPECTED` و quarantine است،
  نه یک تلاش شکست‌خوردهٔ عادی.

## 6. محدودهٔ تغییر (patch scope)

محدوده فقط توصیه نیست؛ پیش از اعمال diff اعتبارسنجی می‌شود:

- مسیرهای خارج از `writable_paths` → رد تغییر.
- عبور از `max_files_changed` یا `max_lines_changed` → توقف و ارجاع به انسان (نشانهٔ اینکه
  وظیفه بد تقسیم شده است).
- حذف فایل آزمون، تغییر baseline، یا تغییر پیکربندی سیاست → `deny` مطلق.

## 7. منطق «حالت» (profile)

سه حالت فقط نام نیستند؛ هر کدام مجموعه‌ای از پیش‌فرض‌های پیکربندی است که **قابل آزمون** است:

| فلگ | quick | standard | advanced |
| --- | --- | --- | --- |
| `acceptance.executable_required` | حداقلی | true | true |
| `verification.independent_rerun` | false | true | true |
| `checkpoint.per_requirement` | false | true | true |
| `sandbox.profile` | default | default | strict |
| `evidence.bundle_required` | false | true | true |

اگر یک حالت نتواند به فلگ نگاشت شود، از سند حذف می‌شود. جدول بدون نگاشت، بازاریابی است.

## 8. سؤال‌های باز این قرارداد

- آیا یک وظیفه می‌تواند چند نیازمندی را پوشش دهد؟ (پیشنهاد: بله، اما فقط اگر همه در یک گیت
  تأیید شوند؛ در غیر این صورت تفکیک شود.)
- سیاست «دسته‌ای‌کردن تأیید انسانی» به چه اندازه‌ای تجمیع کند؟ (پیشنهاد: در مرز هر نیازمندی.)
