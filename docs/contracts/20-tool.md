# قرارداد ۲ — ابزار (Tool Gateway)

نسخه: 0.1 · وابسته به: [00-invariants](00-invariants.md) (I1, I2, I7, I8)

ابزار، تنها سطح اثرگذاری در CSEF است. اگر کاری در این سند تعریف نشده باشد، عامل نمی‌تواند
انجامش دهد — و این محدودیت است، نه نقص.

---

## 1. توصیفگر ابزار

هر ابزار یک توصیفگر ثابت دارد که پیش از اجرا معتبر می‌شود:

```yaml
name: run_tests
version: 1
description_for_model: "اجرای آزمون‌ها در sandbox و بازگرداندن خروجی خام"
effects: [process, read_fs]          # read_fs | write_fs | process | network
capabilities_required: [run_tests]     # نگاشت به سیاست
sandbox:
  required: true
  profile: default
  network: deny
input_schema:  # JSON Schema / Pydantic v2
  type: object
  required: [target, timeout_s]
  properties:
    target: {type: string, pattern: "^[A-Za-z0-9_./:\\[\\]-]{1,400}$"}
    timeout_s: {type: integer, minimum: 1, maximum: 900}
output_schema:
  type: object
  required: [exit_code, stdout_ref, duration_ms]
limits: {timeout_s: 900, max_stdout_bytes: 262144}
idempotency: read_only          # read_only | idempotent | non_idempotent
```

قواعد سخت:

- ثبت ابزار **استاتیک** است. بارگذاری پویا از مخزن یا شبکه ممنوع (I7).
- `input_schema` تنها دروازهٔ ورودی است؛ هیچ ابزاری «رشتهٔ آزاد» نمی‌پذیرد.
- `effects` باید کامل اعلام شود؛ اعلام ناقص = رد ثبت ابزار در تست سازگاری.

## 2. کلاس‌های اثر و معنی مجوز

| effects | معنای عملی | پیش‌فرض سیاست |
| --- | --- | --- |
| `read_fs` | خواندن فایل داخل محدوده | allow |
| `write_fs` | نوشتن در worktree | allow با scope |
| `process` | اجرای فرایند | sandbox اجباری |
| `network` | هر تماس شبکه | ask |
| `write_fs` + مسیر کنترل | نوشتن روی سطح کنترل | deny مطلق |

هیچ ابزاری نمی‌تواند `effects` را در زمان اجرا گسترش دهد.

## 3. هم‌توانی (idempotency)

- `read_only`: تکرار بی‌اثر.
- `idempotent`: تکرار با همان `idempotency_key` باید نتیجهٔ یکسان بدهد؛ آداپتر مسئول است.
- `non_idempotent`: مجاز است، اما تکرار خودکار پس از قطع ممنوع؛ نیازمند تصمیم صریح.

هر فراخوانی `idempotency_key = hash(task_id, tool, normalized_input, attempt_epoch)` دارد.
پس از قطع ناگهانی، فراخوانی بدون رکورد `outcome` به‌عنوان **نامعلوم** علامت می‌خورد (I8) و
رفتار پیش‌فرض `non_idempotent` است تا وقتی خلافش ثابت شود.

## 4. ثبت فراخوانی

```yaml
invocation_id: inv-000431
task_id: T-0042
tool: run_tests
tool_version: 1
attempt: 2
idempotency_key: "..."
input_hash: "sha256:..."
started_at: "..."
ended_at: "..."
outcome: success | failure | unknown | cancelled | denied
exit_code: 0
stdout_ref: "artifact://..."
stderr_ref: "artifact://..."
duration_ms: 4210
sandbox_id: "sbx-..."
cost_usd: 0.0
```

`stdout` بزرگ‌تر از حد به انبار artifact می‌رود و در رکورد فقط ارجاع ثبت می‌شود؛ متن کوتاه‌شده
باید با علامت قطع‌شدگی و اندازهٔ اصلی همراه باشد. کوتاه‌سازی بی‌علامت، تحریف شاهد است.

## 5. طبقه‌بندی خطا (مشترک با سند ۶۰)

هر خطای ابزار باید دقیقاً یکی از این‌ها باشد. ابزاری که خطای طبقه‌بندی‌نشده برساند، در تست
سازگاری رد می‌شود:

`transient` · `policy_denied` · `bad_input` · `environment` · `product_bug` ·
`budget_exhausted` · `timeout` · `cancelled` · `sandbox_violation` · `unknown`

تمایز حیاتی: `transient` (شبکه، rate limit) با `product_bug` (کد اشتباه است) یکی نیست؛ اولی
تلاش مجدد API است، دومی تلاش اصلاح کد. این دو بودجهٔ جدا دارند.

## 6. ابزارهای هستهٔ نسخهٔ اول (حداقل، نه بیشتر)

| ابزار | effects | یادداشت |
| --- | --- | --- |
| `read_file` / `list_dir` | read_fs | محدود به محدودهٔ وظیفه |
| `search_text` / `search_symbol` | read_fs | خروجی رتبه‌بندی‌شده با ارجاع |
| `write_file` / `apply_patch` | write_fs | diff پیش از اعمال اعتبارسنجی می‌شود |
| `run_command` | process | **فقط** allowlist باریک + sandbox |
| `run_tests` | process | آداپتر مخصوص pytest، خروجی ماشین‌خوان |
| `git_status` / `git_diff` | read_fs | برای شواهد و بازبینی |
| `record_claim` | — | ثبت ادعای عامل (شاهد نیست) |

`run_command` عمومی خطرناک‌ترین ابزار است. تا وقتی sandbox واقعی وجود ندارد، باید
`deny` باشد و فقط ابزارهای باریک فعال باشند.

## 7. نکتهٔ امنیتی که نباید فراموش شود

allowlist دستور امنیت نمی‌سازد: `pytest` خودش کد مخزن را اجرا می‌کند و `setup.py` یا
`conftest.py` می‌تواند هر کاری بکند. بنابراین کنترل سه‌لایه است:

1. نام دستور در allowlist،
2. اجرا داخل sandbox با فایل/شبکه/منابع محدود،
3. جداسازی اسرار از محیط اجرا.

هر سه لازم‌اند. دوتای اول بدون سوم، فقط توهم امنیت است.

## 8. سؤال‌های باز

- آیا ابزارهای پروژه‌محور (مثل `alembic upgrade`) باید قابل افزودن توسط کاربر باشند؟
  (پیشنهاد: بله، اما فقط با ویرایش فایل پیکربندی در control plane و تأیید صریح.)
- سیاست پاک‌سازی اسرار: نگاشت جایگزینی پیش از ارسال هر خروجی به مدل، در کدام لایه؟
  (پیشنهاد: در Tool Gateway، پیش از ترک مرز.)
