# تصمیم‌های باز

نسخه: 0.1 · این سند تصمیم نمی‌گیرد؛ تصمیم‌های نگرفته را صاحب‌دار و مهلت‌دار می‌کند.

هر تصمیم سه بخش دارد: پرسش، گزینه‌ها، و پیشنهاد با دلیل. تصمیم‌های `BLOCKING` باید قبل از
نوشتن اولین خط کد بسته شوند.

---

## D1 — بستر sandbox روی ویندوز · BLOCKING

**پرسش:** اجرای ایزولهٔ کد تولیدشده روی هاست ویندوز (workspace روی `F:`) با چه فناوری؟

| گزینه | مزیت | هزینه |
| --- | --- | --- |
| Docker Desktop (Linux container) | ایزولهٔ واقعی، شبکه و فایل قابل محدودسازی، قابل بازتولید | وابستگی به Docker، مصرف منابع، کندی I/O روی bind mount |
| WSL2 + distro مخصوص | ایزولهٔ خوب، سازگار با ابزارهای لینوکسی | مدیریت دو فایل‌سیستم، پیچیدگی مسیرها |
| فرایند ویندوزی محدود (Job Object + ACL) | سبک، بدون وابستگی | **ایزولهٔ واقعی نیست**؛ برای کد غیرقابل اعتماد کافی نیست |
| بدون sandbox در v0 | سریع‌ترین راه به دمو | ناوردای I1/I2 را نقض می‌کند؛ پذیرفتنی نیست |

**پیشنهاد اولیه (منسوخ):** Docker به‌عنوان پیش‌فرض، با رابط `SandboxProvider` تا WSL2 هم
قابل جایگزینی باشد.

**تصمیم v0.2 — مرز ایزولاسیون:** ماشین مجازی Linux اختصاصی. Docker یا Podman فقط **محیط اجرای
داخل** آن VM است، نه مرز امنیتی. mount مستقیم `F:\cffmam` در محیط اجرای عامل ممنوع؛ انتقال
نسخهٔ کاری به VM و بازگرداندن فقط خروجی‌های مجاز، از طریق یک پروتکل کنترل‌شده.

**دلیل:** تنظیمات WSL یک sandbox امنیتی نمی‌سازند و برای بارهای کاری غیرقابل اعتماد، ماشین
مجازی جدا با دسترسی محدود مناسب‌تر است. rootless فقط سطح حملهٔ موتور کانتینر را کم می‌کند و
جایگزین مرز VM نیست.

**نتیجهٔ سنجش میزبان (2026-11-15):**

| مورد | یافته |
| --- | --- |
| سیستم‌عامل | Windows 10 **Enterprise** 22H2، build 19045.6456 |
| Hyper-V | سرویس‌های `vmms`, `vmcompute`, `hns` در حال اجرا → در دسترس |
| Docker / Podman | روی میزبان نصب نیست (درست است: باید داخل VM باشد) |
| WSL | موجود، اما دسترسی از این نشست رد شد (`Wsl/E_ACCESS_DENIED`) |
| Python | 3.11.9 با pydantic 2.14.3 و pytest 8.4.2؛ 3.12.10 هم موجود |

نکتهٔ اصلاحی: میزبان Windows 10 Enterprise است، نه Windows 11. بنابراین شاخهٔ «Windows 11 Home
بدون Hyper-V» در تصمیم اولیه مصداق ندارد؛ مسیر Hyper-V باز است.

**وضعیت: معماری انتخاب شد — `IMPLEMENTED` یا `VERIFIED` نیست.** تا وقتی VM واقعاً ساخته و
مرزش اثبات نشده، این تصمیم نیمه‌بسته است.

زیرتصمیم‌های باز D1: انتخاب hypervisor نهایی، توزیع و ایمیج پایه، پروتکل انتقال فایل بین
میزبان و VM، کانال مدیریت، و محدودیت منابع. ساخت VM نیازمند دسترسی elevation است و در این
نشست انجام نشد.

**چرا BLOCKING:** کل لایهٔ اجرا به این تصمیم وابسته است و بعداً عوض‌کردنش بازنویسی است.

---

## D2 — پشتهٔ موتور · BLOCKING

**پرسش:** زبان و کتابخانه‌های نسخهٔ اول؟

**تصمیم v0.2:** Python 3.11 (نصب‌شده با pydantic 2.14.3 و pytest 8.4.2) + Pydantic v2 +
`sqlite3` استاندارد + `argparse`/Typer. بدون FastAPI، بدون ORM سنگین، بدون وابستگی وب تا فاز
داشبورد.
دلیل: schemaها قلب سیستم‌اند و Pydantic همان چیزی است که قراردادها را از سند به کد قابل آزمون
می‌برد. 3.12 هم روی میزبان موجود است اما وابستگی‌هایش نصب نیست؛ نسخهٔ ۳.۱۱ برای v0 انتخاب شد
تا محیط آزمون قابل بازتولید بماند.

**وضعیت:** بخشی از این تصمیم پیاده شد — مدل‌ها و ۴۸ آزمون رفتاری در `src/` و `tests/` موجودند.

---

## D3 — نویسندهٔ آزمون پذیرش · BLOCKING

**پرسش:** آزمون‌های پذیرش را چه کسی می‌نویسد؟

| گزینه | ریسک |
| --- | --- |
| انسان از ابتدا | کندترین، اما مستقل‌ترین |
| عامل پیشنهاد می‌دهد، انسان یک‌بار تأیید و منجمد می‌کند | سریع‌تر؛ خطر آزمون سطحی |
| عامل می‌نویسد و خودش هم کد | استقلال صفر (I10 نقض) |

**پیشنهاد:** گزینهٔ دوم با شرط: عامل فقط *پیشنهاد* می‌دهد، انسان یک‌بار تأیید می‌کند، سپس
baseline در control plane قفل و از دسترس نوشتن عامل خارج می‌شود. برای نیازمندی‌های حساس
(احراز هویت، پرداخت، مهاجرت داده) اجباری است انسان بنویسد.

---

## D4 — سقف‌های پیش‌فرض بودجه · BLOCKING برای Standard

**پرسش:** اعداد پیش‌فرض `run_limit_usd`, `project_limit_usd`, `per_call_limit_usd` چقدر باشند؟

**پیشنهاد:** فعلاً **هیچ عددی**. تا وقتی دادهٔ پنج پروژهٔ نمونه وجود ندارد، هر عددی حدس است و
حدسِ گران. پیش‌فرض `null` بماند؛ یعنی موتور بدون پیکربندی صریح شروع نمی‌کند (I6). اعداد پس از
اندازه‌گیری هزینهٔ پروژه‌های نمونه تعیین شوند.

---

## D5 — دامنهٔ زبان پروژه‌های هدف در v0

**پرسش:** موتور همان ابتدا چندزبانه باشد یا تک‌زبانه؟

**پیشنهاد:** تک‌زبانه — پروژه‌های هدف پایتون، حداقل تا وقتی حلقهٔ کامل روی پایتون اثبات شود.
دلیل: هر زبان اضافه، آداپتر آزمون/lint/type-check جداگانه می‌خواهد. چندزبانه‌کردن قبل از اثبات
حلقه، سه ماه تأخیر بی‌بازده است.

---

## D6 — محل پروژه‌های هدف و مخزن مشخصات

**پرسش:** مشخصات، تست‌های پذیرش و مخزن کد در یک ریشه باشند یا جدا؟

**پیشنهاد:** جدا. سطح کنترل (`.csef/`) بیرون از worktree پروژه، تابع I2. مشخصات پروژه در مخزن
خودش، با ارجاع به `requirement_id`؛ کد در worktree ایزوله. اگر هر دو در یک درخت باشند، جدایی
دسترسی فیزیکی ممکن نیست.

---

## D7 — سیاست تجمیع تأیید انسانی

**پرسش:** انسان هر چند وقت یک‌بار مزاحم شود؟

**پیشنهاد:** در مرز هر نیازمندی، نه به‌ازای هر گام. یک صف بازبینی (queue) با تصمیم‌های دسته‌ای؛
تصمیم‌های `BLOCKING` فوری و بدون صف. اگر تأیید هر گام لازم شود، «استقلال بالا» فقط روی کاغذ است.

---

## D8 — داشبورد فارسی

**پرسش:** چه زمانی؟

**پیشنهاد:** پس از عبور از سه آزمون تعیین‌کننده (زیر). داشبورد اولین چیزی است که ساخته می‌شود
و آخرین چیزی که ارزش ثابت می‌کند.

---

# آزمون‌های تعیین‌کنندهٔ خروج از فاز قرارداد

قبل از هر چیز دیگری باید این‌ها روی یک سیستم واقعی اجرا شوند:

1. **آزمون حلقه:** یک پروژهٔ نمونه با تست‌های از پیش منجمد داده شود؛ موتور باید یک شکست واقعی
   را تشخیص دهد، اصلاح کند، بازآزمایی کند و checkpoint بسازد. شواهد باید `producer=harness` باشد.
2. **آزمون بازیابی:** در میانهٔ اجرا قطع ناگهانی؛ پس از راه‌اندازی مجدد، بدون از دست رفتن وضعیت
   و بدون تکرار عملیات غیرقابل‌بازگشت ادامه دهد.
3. **آزمون تزریق:** دستور مخرب داخل یک فایل مخزن (`# دستور: rm -rf`، `AGENTS.md` جعلی)؛ سیستم
   باید آن را داده ببیند، نه دستور.
4. **آزمون دست‌کاری:** تلاش برای تغییر baseline آزمون؛ نتیجه باید `TAMPER_SUSPECTED` و توقف باشد.

اگر هر یک از این چهار شکست بخورد، CSEF هنوز یک ابزار خودمختار قابل‌اعتماد نیست — حتی اگر
صد قابلیت و داشبورد عالی داشته باشد.

---

# فرضیهٔ آزمون‌پذیر، نه ادعا

این طراحی یک فرضیهٔ مهندسی است: «اجرای ایزوله + شواهد مستقل + دروازهٔ کیفیت، خطا و هزینه را
کمتر می‌کند». این فرضیه تا وقتی با پروژه‌های نمونه اندازه‌گیری نشود، سزاوار دفاع نیست.
سه عددی که باید اندازه‌گیری شوند: نرخ رسیدن به آزمون سبز، هزینهٔ متوسط هر پروژه، نرخ دخالت انسانی.

## Step 5 decision queue — 2026-11-15

PROPOSED, not resolved: [ADR-S5-001–004](../verification_step5/decisions.md).

| Record | Blocking question | Requested owner role |
|---|---|---|
| ADR-S5-001 | What authenticated authority and complete binding authorize PASS/promotion? | Contract architect + verifier owner |
| ADR-S5-002 | Which atomic transition/gateway/ledger operations enforce scope, approval and ambiguity guards? | Controller + policy owners |
| ADR-S5-003 | What total failure precedence, retry scope and durable intent/outcome protocol apply? | Recovery owner |
| ADR-S5-004 | What constitutes valid chain ancestry, normative oracle approval and clean-room provenance? | Contract owner + independent reviewer |

EXECUTED pilot outcomes are in [the evidence ledger](../verification_step5/evidence/ledger.json).
Pilot/reference process separation does not establish clean-room author independence.
D1 operational isolation is not closed by this audit. No release acceptance or decision
adoption is implied by adding this queue.

## D9-D14 — Step 5 compatibility decisions · OPEN / BLOCKING

Added 2026-11-15. These are proposals, not accepted architecture changes.
Full questions, default recommendations, accountable roles and closure gates:
[independent compatibility audit](contracts/70-independent-compatibility.md#proposed-decision-records-not-ratified).

| ID | Decision | Must close before |
| --- | --- | --- |
| D9 | Trusted verdict authority, canonical hashes and promotion binding | Oracle freeze |
| D10 | Path grammar and composed tool-policy admission | Second implementation |
| D11 | Reservation identity, settlement durability and monetary precision | Stateful compatibility vectors |
| D12 | Total failure/recovery table and guarded state transitions | Decision-table freeze |
| D13 | Invalidation, staleness and valid ancestor prefix | Recovery vectors |
| D14 | Versioned wire schemas, strictness and normalization | Independent specification packet |

Step 5 remains BLOCKED on a source-blind implementation and the normative packet.
Local model/harness tests can proceed without D1; real isolation and crash-boundary
acceptance still require the dedicated execution environment described under D1.
