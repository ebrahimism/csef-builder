# قرارداد صفر — ناورداها

نسخه: 0.1 · وضعیت: پیش‌نویس برای بازبینی

این سند پایهٔ بقیهٔ قراردادهاست. اگر یک پیاده‌سازی با یکی از این ناورداها در تضاد باشد،
پیاده‌سازی غلط است، نه سند. هر ناوردا سه بخش دارد: حکم، دلیل، و **سازوکار اجرا و تشخیص نقض**.
ناوردایی که نتوان نقضش را تشخیص داد، آرزو است نه ناوردا.

---

### I1 — هیچ اثر جانبی بدون دروازهٔ ابزار

**حکم:** مدل هرگز مستقیماً اثری روی سیستم نمی‌گذارد. خروجی مدل فقط «قصد» (intent) است؛ اثر
تنها از طریق Tool Gateway و پس از مجوز سیاست اعمال می‌شود.

**دلیل:** هر مسیر اثری که از دروازه عبور نکند، از ثبت، بودجه، مجوز و شواهد خارج می‌شود.

**اجرا/تشخیص:** هیچ آداپتر مدلی به `subprocess`، شبکه، یا فایل‌سیستم دسترسی ندارد؛ فقط به یک
تابع `propose(intent)` دسترسی دارد. تشخیص نقض: بازرسی وابستگی‌های ماژول (import graph) — اگر
ماژول مدل به لایهٔ اجرا import داشته باشد، تست معماری شکست می‌خورد.

---

### I2 — جدایی سطح کنترل از سطح داده

**حکم:** دامنهٔ نوشتن عامل محدود به worktree پروژه است. مسیرهای زیر **همیشه** خارج از دسترسی
نوشتن عامل‌اند: آزمون‌های پذیرش پایه، فایل سیاست، انبار شواهد، پایگاه journal، پیکربندی sandbox،
و خود CSEF.

**دلیل:** اگر عامل بتواند سیاست یا آزمون را تغییر دهد، «استقلال در محدودهٔ مجاز» به «تعریف
محدوده توسط خودش» تبدیل می‌شود.

**اجرا/تشخیص:** دو ریشهٔ فیزیکی جدا (control plane و data plane) با ACL متفاوت؛ agent process با
هویت کاربر متفاوت اجرا می‌شود. تشخیص نقض: بازرسی hash فایل‌های control plane پیش و پس از هر
اجرا؛ هر تغییر = حادثهٔ امنیتی.

---

### I3 — شاهد را harness می‌سازد، نه عامل

**حکم:** هر شاهد (خروجی آزمون، exit code، artifact، اثر انگشت محیط) توسط harness ضبط می‌شود.
عامل می‌تواند «ادعا» بسازد؛ ادعا شاهد نیست و در محاسبهٔ حکم هیچ وزنی ندارد.

**دلیل:** اگر عامل گزارش بنویسد، می‌تواند گزارش سبز جعلی بنویسد و کل دروازهٔ بازبینی بی‌اثر شود.

**اجرا/تشخیص:** Evidence Store فقط از یک نویسنده (harness) می‌پذیرد؛ هر شاهد علاوه بر محتوا،
`producer=harness` و شناسهٔ فراخوانی ابزار را حمل می‌کند. تشخیص نقض: شاهدی که `producer` آن
harness نیست یا `invocation_id` معتبر ندارد، در محاسبهٔ حکم رد می‌شود (fail-closed).

---

### I4 — checkpoint فقط با حکم PASS

**حکم:** فقط Controller می‌تواند checkpoint بسازد، و فقط وقتی verdict نهایی برای همهٔ معیارهای
الزامی آن وظیفه `PASS` باشد. نه عامل، نه آداپتر ابزار، نه آداپتر مدل.

**دلیل:** نقطهٔ بازیابی معتبر، دارایی اصلی سیستم است؛ اگر آلوده شود، کل تاریخ پروژه بی‌اعتبار می‌شود.

**اجرا/تشخیص:** ساخت checkpoint نیازمند یک «مجوز امضا‌شده» از Verifier است که به
`(task_id, source_revision, evidence_bundle_hash)` گره خورده. تشخیص نقض: هر checkpoint بدون
این سه‌گانه، در زمان `csef verify` رد می‌شود.

---

### I5 — آزمون پذیرش قبل از پیاده‌سازی منجمد می‌شود

**حکم:** معیارهای پذیرش قطعی باید پیش از شروع پیاده‌سازی وجود داشته باشند، در یک baseline
hash-قفل شوند، و تغییر آن‌ها نیازمند تأیید انسانی + نسخهٔ جدید نیازمندی + **باطل‌شدن شواهد قبلی**
است.

**دلیل:** آزمونی که بعد از کد نوشته شود، کد را تأیید می‌کند نه نیازمندی را.

**اجرا/تشخیص:** baseline در control plane و با `hash` ثبت می‌شود؛ Verifier پیش از هر اجرا hash
را بازمی‌خواند. تشخیص نقض: اختلاف hash → اجرا متوقف و وضعیت `TAMPER_SUSPECTED`.

---

### I6 — پیش‌فرض‌های fail-closed

**حکم:** سیاست ناشناخته = `deny`. بودجهٔ `null` = «تنظیم‌نشده» و به معنی «بی‌نهایت» نیست؛
شروع هر عملیات هزینه‌دار تا وقتی سقف صریح تنظیم نشده ممنوع است. شاهد ناقص = `FAIL`، نه `PASS`.

**دلیل:** هر پیش‌فرض باز، در عمل به رفتار باز تبدیل می‌شود.

**اجرا/تشخیص:** تحلیل پیکربندی هنگام بارگذاری؛ اجرا با پیکربندی ناقص اصلاً شروع نمی‌شود.

---

### I7 — محتوای غیرقابل اعتماد، داده است نه دستور

**حکم:** محتوای فایل‌های مخزن، خروجی ابزارها، صفحات وب و اسناد، همگی «داده» هستند.
هیچ دستوری از این منابع وارد کانال دستور (system/developer) نمی‌شود و به‌عنوان درخواست کاربر
تفسیر نمی‌گردد.

**دلیل:** مخزن و وب کانال تزریق دستور هستند؛ عاملی که کد را می‌خواند و اجرا می‌کند، هدف طبیعی است.

**اجرا/تشخیص:** کانال‌های context به‌صورت نوع‌دار تفکیک می‌شوند (`trusted_instruction` در برابر
`untrusted_data`) و هنگام ساخت prompt برچسب می‌خورند. تشخیص نقض: تست تزریق با دستور مخرب
داخل فایل مخزن؛ سیستم باید آن را به‌عنوان داده ببیند، نه اقدام.

---

### I8 — journal پیش از اثر (write-ahead)

**حکم:** هر گذار وضعیت و هر فراخوانی ابزار، **قبل** از اعمال اثر با یک `idempotency_key` در
journal ثبت می‌شود. اثر پس از ثبت رخ می‌دهد، و نتیجه پس از اثر ثبت می‌شود.

**دلیل:** بدون این ترتیب، قطع ناگهانی یا اثر گم‌شده یا اثر تکراری تولید می‌کند.

**اجرا/تشخیص:** دو رکورد به‌ازای هر فراخوانی (`intent` سپس `outcome`). تشخیص نقض: رکورد
`intent` بدون `outcome` پس از راه‌اندازی مجدد = فراخوانی مشکوک؛ باید به‌عنوان «نامعلوم» علامت
بخورد، نه «موفق» و نه «ناموفق».

---

### I9 — یک نویسنده به‌ازای هر worktree

**حکم:** در هر لحظه فقط یک نویسنده (یک وظیفه) روی یک worktree مجاز است. این محدودیت با
**lease** در پایگاه وضعیت اعمال می‌شود، نه با عادت و مستندسازی.

**دلیل:** دو نویسندهٔ هم‌زمان روی یک درخت = ویرایش گم‌شده و checkpoint آلوده.

**اجرا/تشخیص:** lease با `owner`, `expires_at`, `fencing_token`. هر نوشتن باید fencing token
معتبر ارائه دهد. تشخیص نقض: token قدیمی → رد نوشتن.

---

### I10 — استقلال، ساختاری است نه نظری

**حکم:** بازبینی مستقل یعنی اجرای مجدد معیارهای قطعی روی یک **checkout تمیز** با آزمون‌های
hash-تأییدشده و محیط تازه. نظر یک مدل دیگر شاهد مستقل نیست و به‌تنهایی نمی‌تواند حکم بسازد.

**دلیل:** دو مدل که هم‌خطا باشند، استقلال تولید نمی‌کنند؛ فقط توهم اطمینان می‌سازند.

**اجرا/تشخیص:** Verifier همیشه از snapshot تمیز اجرا می‌کند، هرگز از worktree آلودهٔ عامل.
تشخیص نقض: اگر Verifier روی درخت دارای تغییرات تأییدنشده اجرا شود، حکم باطل است.

---

### I11 — هر checkpoint بازتولیدپذیر است

**حکم:** دستور `csef verify <checkpoint>` باید بدون دخالت عامل، همهٔ معیارهای قطعی آن checkpoint
را دوباره اجرا کند و همان نتیجه را بگیرد.

**دلیل:** checkpointی که نتوان بازتولیدش کرد، یک ادعاست نه یک واقعیت.

**اجرا/تشخیص:** اگر بازاجرا `FAIL` بدهد یا به‌دلیل drift محیط قابل اجرا نباشد، checkpoint
`STALE` می‌شود (پاک نمی‌شود، علامت می‌خورد) و زنجیره از آن عبور نمی‌کند.

---

### I12 — ابهام، شکست است نه اجازهٔ حدس

**حکم:** وقتی مشخصات برای یک تصمیم کافی نیست، عامل باید متوقف شود و پرسش بسازد
(`BLOCKED_ON_AMBIGUITY`). حدس زدن دربارهٔ نیازمندی، تخلف است.

**دلیل:** گران‌ترین بازکاری‌ها از فرض‌های معقول اما نادرست می‌آیند؛ و این خطا در بازبینی کد دیده
نمی‌شود، چون کد از فرض خودش درست است.

**اجرا/تشخیص:** Planner باید برای هر وظیفه فهرست «تصمیم‌های باز» تولید کند؛ اگر تصمیمی هم
اثر معماری دارد و هم در مشخصات نیست، وظیفه بدون ورودی انسانی مجاز به ورود به `EXECUTING` نیست.

---

## ناورداهای تثبیت‌شده در بازبینی v0.2

سه قاعدهٔ زیر در بازبینی دوم به‌عنوان ناوردای مستقل و غیرقابل مذاکره ثبت شدند. هر سه از
I3/I10/I12 مشتق می‌شوند، اما شناسهٔ مستقل دارند چون **شرط پذیرش** مشخصی دارند که باید با
آزمون اثبات شود، نه با متن.

### I13 — EVIDENCE-AUTHORITY

**حکم:** شاهد معتبر فقط توسط Harness مورد اعتماد ثبت می‌شود.

**شرط پذیرش:** فایل گزارشی که عامل ساخته، بدون رکورد اجرای Harness، هیچ حکم قبولی ایجاد نکند.

**اجرا:** `EvidenceRecord.producer` یک `Literal[Producer.HARNESS]` است، نه فیلد آزاد. یعنی
شاهد جعلی پیش از آن‌که سؤال سیاست باشد، خطای نوع است و اصلاً ساخته نمی‌شود.
از DEC-001 به بعد، برچسب `harness` هم کافی نیست: هر شاهد باید به رکورد اجرای متناظر در
`HarnessJournal` بپیوندد و حکم فقط از `Controller.verify` بیرون می‌آید.

**آزمون:** `tests/test_evidence_contract.py::test_agent_produced_evidence_cannot_be_constructed` و
`tests/test_evidence_contract.py::test_harness_label_without_execution_record_yields_fail`

### I14 — VERIFY-INDEPENDENCE

**حکم:** بستهٔ آزمون پذیرش باید منجمد، خارج از محدودهٔ نوشتن عامل و دارای hash تأییدشده باشد.

**شرط پذیرش:** تغییر حتی یک بایت از بستهٔ آزمون، پذیرش را متوقف کند.

**اجرا:** `baseline_hash` در `AcceptanceSpec` نگه داشته می‌شود، در `compute_verdict` و `promote`
با hash بستهٔ شواهد مقایسه می‌شود، و اختلاف به `TAMPER_SUSPECTED` می‌رسد.

**آزمون:** `tests/test_evidence_contract.py::test_tampered_baseline_is_detected` و
`tests/test_checkpoint_contract.py::test_bundle_from_another_baseline_is_refused`

### I15 — AMBIGUITY-BLOCK

**حکم:** ابهام مؤثر بر قرارداد یا رفتار مورد انتظار، مانع اجرا است.

**شرط پذیرش:** عامل نتواند با فرض‌سازی خودکار وضعیت را به `RUNNING` منتقل کند.

**اجرا:** `Task.assert_ready_to_execute` با `open_decisions` غیرخالی رد می‌کند، و
`AmbiguityBlock.guessed` یک `Literal[False]` است.

**آزمون:** `tests/test_task_contract.py::test_ambiguity_blocks_execution` و
`tests/test_failure_contract.py::test_ambiguity_block_cannot_claim_a_guess`

---

## معیار خروج نهایی از مرحلهٔ قرارداد

اگر نتوان با یک fixture ثابت ثابت کرد که **یک عامل متقلب، یک آزمون دست‌کاری‌شده یا یک اجرای
نیمه‌کاره نمی‌تواند checkpoint معتبر بسازد**، مرحلهٔ قراردادها تمام نشده است.
این معیار با `tests/test_evidence_contract.py` و `tests/test_checkpoint_contract.py` پوشش داده
شده است؛ عبور از آن شرط لازم است، نه شرط کافی.

## Step 5 audit qualification — 2026-11-15

EXECUTED audit evidence: [program and ledger](../../verification_step5/PROGRAM.md).
The preceding implementation/test references describe partial checks, not end-to-end
enforcement of the exit criterion. In particular:

- I13: rejecting `producer=agent` validates a label; it does not authenticate a writer.
  Metadata labeled `harness` can yield PASS without a trusted invocation record (probe a01).
- I14: comparing supplied hashes does not establish hashing of actual acceptance bytes,
  protected storage, a clean checkout or resistance to a change between check and use.
- I15: `assert_ready_to_execute` rejects open decisions, but direct
  `transition(EXECUTING)` bypasses that guard (probe a10). `RUNNING` above needs an explicit
  mapping to `EXECUTING` in the adopted contract vocabulary.

These findings do not weaken the invariants. Proposed enforcement decisions are in
[ADR-S5-001–004](../../verification_step5/decisions.md); they are not adopted by this addendum.

## Independent audit addendum — 2026-11-15

EXECUTED: the independent audit in [70-independent-compatibility](70-independent-compatibility.md)
reproduces gaps in I13-I15 enforcement. The tests cited above check labels and
explicit helper calls; they do not prove authenticated provenance, acceptance-byte
integrity or mandatory execution guards. In particular, `transition(EXECUTING)`
bypasses `assert_ready_to_execute`. `RUNNING` above refers to `EXECUTING` in the model.
The acceptance obligations remain unchanged; their complete enforcement is unverified.
