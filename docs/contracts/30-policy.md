# قرارداد ۳ — سیاست و بودجه (Policy + Budget)

نسخه: 0.1 · وابسته به: [00-invariants](00-invariants.md) (I2, I6, I9)

سیاست، پاسخ ماشین‌خوان به این سؤال است: «عامل در محدودهٔ مجاز چه کاری می‌تواند بکند؟»
و بودجه پاسخ به این: «تا کجا؟»

دو قاعدهٔ مطلق:

1. **عامل نمی‌تواند سیاست را تغییر دهد** — نه فایل، نه از طریق ابزار، نه با درخواست از خودش.
2. **`null` یعنی تنظیم‌نشده، نه بی‌نهایت** (I6).

---

## 1. ساختار فایل

```yaml
policy_version: 1
policy_hash: "sha256:..."          # در هر checkpoint و شاهد ثبت می‌شود

execution:
  default: deny                     # allow | ask | deny
  on_unknown_capability: deny

tools:
  read_repository:   {decision: allow}
  edit_project_files: {decision: allow, scope: isolated_worktree,
                       paths: ["src/**", "tests/**"]}
  run_tests:         {decision: allow, sandbox_required: true, network: deny}
  install_dependencies: {decision: ask, network_required: true, once_per_task: true}
  run_command:       {decision: deny}
  delete_project:    {decision: deny}
  deploy_production: {decision: ask}

budgets:
  run_limit_usd: 1.00               # سقف یک وظیفه
  project_limit_usd: 25.00          # سقف تجمعی پروژه
  per_call_limit_usd: 0.20
  on_limit: stop                    # stop | downgrade

recovery:
  max_patch_attempts: 3
  rollback_on_failed_validation: true
  max_identical_failures: 2

protection:
  immutable_paths:
    - ".csef/policy.yaml"
    - ".csef/acceptance/**"
    - ".csef/evidence/**"
    - ".csef/journal.db"
```

## 2. معنای تصمیم‌ها

| تصمیم | معنا | چه کسی ادامه می‌دهد |
| --- | --- | --- |
| `allow` | اجرا مجاز است | موتور |
| `ask` | تا تأیید صریح انسانی، ممنوع | انسان، با امضای گره‌خورده به فراخوانی |
| `deny` | هرگز، بدون استثنا در همان نسخهٔ سیاست | هیچ‌کس |

**اولویت:** `deny` > `ask` > `allow`. اگر چند قاعده با یک capability منطبق شوند، سخت‌گیرانه‌ترین
برنده است. هیچ قاعده‌ای نمی‌تواند `deny` را نرم کند.

## 3. تأیید انسانی چگونه معتبر می‌شود (و چطور replay نشود)

تأیید یک «بله» شفاهی نیست؛ یک رکورد است:

```yaml
approval_id: apr-0007
invocation_hash: "sha256:..."      # دقیقاً همان فراخوانی درخواست‌شده
capability: install_dependencies
scope: {task_id: T-0042, command_hash: "sha256:..."}
granted_by: human:kp
granted_at: "..."
expires_at: "..."
max_uses: 1
```

قواعد:

- تأیید به **hash دقیق** فراخوانی گره می‌خورد؛ تغییر یک کاراکتر در دستور = تأیید باطل.
- `max_uses` پیش‌فرض ۱. تأیید عمومیِ «هرچه خواستی نصب کن» پذیرفته نیست.
- تأیید منقضی‌شده معتبر نیست.
- عامل نمی‌تواند رکورد تأیید بسازد؛ فقط harness.

## 4. بودجه: سه سؤال که بدون پاسخ، بودجه وجود ندارد

هر عملیات هزینه‌دار پیش از اجرا باید جواب این سه را بدهد:

1. **برآورد پیش‌پرواز:** حد بالای هزینهٔ این فراخوانی چقدر است؟
2. **رزرو:** آیا با احتساب رزروهای فعال، سقف‌ها رعایت می‌شوند؟
3. **تسویه:** هزینهٔ واقعی چقدر شد و از کدام سقف کسر شد؟

بدون رزرو، دو فراخوانی موازی می‌توانند هر دو «زیر سقف» باشند و با هم سقف را رد کنند.
مدل حسابداری: `reserve → execute → commit/rollback`.

- `per_call_limit_usd`: اگر برآورد بالاتر از این باشد، فراخوانی رد می‌شود.
- `on_limit: stop` → توقف تمیز با وضعیت `BUDGET_EXHAUSTED` و گزارش.
- `on_limit: downgrade` → **فقط** به مدل‌های از پیش تأییدشده در یک زنجیرهٔ صریح؛ هیچ افت
  خودکار به مدل ارزان‌تر بدون تعریف زنجیره مجاز نیست، چون کیفیت را بی‌صدا عوض می‌کند.
- بودجهٔ هزینه با بودجهٔ تلاش اصلاح جدا حساب می‌شود (سند ۱۰).

## 5. محدودهٔ مسیر

- `paths` با glob تطبیق داده می‌شود، ولی تطبیق پیش از نوشتن و روی مسیر **حل‌شده و نرمال‌شده**
  انجام می‌شود (نه رشتهٔ خام). `..`، symlink و مسیر مطلق ممنوع.
- `immutable_paths` همیشه برنده است، حتی اگر glob دیگری allow بدهد (I2).
- نوشتن روی فایل‌های خارج از worktree = `sandbox_violation`، نه `policy_denied`.

## 6. تغییر سیاست

- فایل سیاست فقط با ویرایش انسانی در control plane تغییر می‌کند.
- هر تغییر `policy_version` را بالا می‌برد و `policy_hash` جدید تولید می‌کند.
- checkpointهایی که با نسخهٔ قدیمی ساخته شده‌اند معتبر می‌مانند اما علامت
  `policy_version_at_creation` را حمل می‌کنند.
- افزایش مجوز بدون تأیید انسانی = حادثهٔ امنیتی، ثبت و توقف.

## 7. سؤال‌های باز

- `deploy_production` در یک ابزار شخصی اصلاً باید وجود داشته باشد؟ (پیشنهاد: فقط اگر پروژه
  صریحاً درخواست کند؛ پیش‌فرض `deny`.)
- سقف‌های پیش‌فرض چه اعدادی باشند؟ عدد باید از دادهٔ پروژه‌های نمونه بیاید، نه از حس.
  تا آن زمان `null` و اجباری‌بودن تنظیم دستی.
