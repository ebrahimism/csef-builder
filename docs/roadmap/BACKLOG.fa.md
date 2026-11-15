# backlog اجرایی CSEF

همهٔ کارهای زیر **برنامه‌ریزی‌شده‌اند**. شمارهٔ task ترتیب مطلق اجرا نیست؛ وابستگی‌ها ملاک‌اند. هیچ زمان یا هزینهٔ قطعی بدون ظرفیت و محیط واقعی تعیین نشده است. وضعیت امروز و نقشهٔ کلی در [سند اصلی](../MASTER-PLAN.fa.md) آمده است.

## T001 — تثبیت خط مبنا و وضعیت Git

- فاز: **F0**
- وابستگی: ندارد؛ هدف‌ها: REQ-104، REQ-106
- دامنه: ثبت نسخهٔ فعلی، شواهد، فایل‌های موجود و موارد ناقص؛ ایجاد تاریخچهٔ کد با حفظ همهٔ فایل‌ها.
- فایل‌های هدف: `docs/evidence/baseline-vnext/manifest.json`
- آزمون پیشنهادی: `tests/integration/test_baseline_inventory.py`
- معیار پایان: گزارش مبنا قابل بازتولید باشد؛ وضعیت ۱۳۳ آزمون دوباره در محیط ثابت ثبت شود؛ هیچ فایل کاربر حذف نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T002 — آزمایش استفادهٔ مجدد از Spec Kit

- فاز: **F0**
- وابستگی: T001؛ هدف‌ها: REQ-101، REQ-106
- دامنه: import/export نمونهٔ واقعی و اجرای گردش‌کار محدود؛ آزمون مرز اختیار و بازیابی.
- فایل‌های هدف: `src/csef_gate/integrations/spec_kit.py`، `integrations/spec-kit/preset/README.md`، `integrations/spec-kit/workflows/csef-review.yml`
- آزمون پیشنهادی: `tests/integrations/test_spec_kit_roundtrip.py`
- معیار پایان: اسناد نیاز و شناسه‌ها round-trip شوند؛ resume باعث تأیید جعلی یا اثر خارجی تکراری نشود؛ تصمیم استفاده/عدم استفاده ثبت شود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T003 — قراردادهای داده و پایگاه کنترل واحد

- فاز: **F1**
- وابستگی: T001؛ هدف‌ها: REQ-104، REQ-106
- دامنه: مدل‌های نسخه‌دار و مهاجرت از دو مخزن فعلی به یک منبع اختیار.
- فایل‌های هدف: `src/csef_gate/contracts.py`، `src/csef_gate/persistence/sqlite.py`، `src/csef_gate/persistence/migrations.py`، `schemas/project-v1.json`، `schemas/stage-v1.json`، `schemas/proposal-v1.json`، `schemas/verification-v1.json`
- آزمون پیشنهادی: `tests/persistence/test_migrations.py`
- معیار پایان: پروژه و شواهد قدیمی حفظ شوند؛ migration تکرارپذیر و قابل بازگشت باشد؛ ورودی ناشناخته نتواند PASS بسازد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T004 — ثبت رویداد، artifact و قفل اجرای هم‌زمان

- فاز: **F1**
- وابستگی: T003؛ هدف‌ها: REQ-104، REQ-106
- دامنه: مخزن محتوایی، event journal، lease و intent/outcome.
- فایل‌های هدف: `src/csef_gate/persistence/artifacts.py`، `src/csef_gate/persistence/events.py`، `src/csef_gate/persistence/leases.py`
- آزمون پیشنهادی: `tests/persistence/test_crash_and_leases.py`
- معیار پایان: دو کنترل‌کننده نتوانند یک مرحله را هم‌زمان مصرف کنند؛ قطع اجرا اختیار تأیید باقی نگذارد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T005 — نیازمندی و تصمیم با منشأ مشخص

- فاز: **F1**
- وابستگی: T003؛ هدف‌ها: REQ-104، REQ-106
- دامنه: تفکیک گفتهٔ کاربر، فرض، پیشنهاد، تصمیم پذیرفته و نسخهٔ منسوخ.
- فایل‌های هدف: `src/csef_gate/lifecycle/projects.py`، `src/csef_gate/lifecycle/requirements.py`، `src/csef_gate/lifecycle/decisions.py`
- آزمون پیشنهادی: `tests/lifecycle/test_fact_authority.py`
- معیار پایان: پیشنهاد مدل نتواند هدف پذیرفته را عوض کند؛ هر تغییر منشأ و نسخه و آثار مشخص داشته باشد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T006 — پرسش و پاسخ پایدار و قابل ویرایش

- فاز: **F1**
- وابستگی: T005؛ هدف‌ها: REQ-103، REQ-104
- دامنه: پرسش معنادار، تشخیص سؤال پاسخ‌داده‌شده، ثبت اصلاح پاسخ و تعارض.
- فایل‌های هدف: `src/csef_gate/lifecycle/questions.py`
- آزمون پیشنهادی: `tests/lifecycle/test_question_revisions.py`
- معیار پایان: پاسخ ویرایش‌شده به نیاز متناظر وصل شود؛ سؤال قدیمی با پاسخ معلوم تکرار نشود؛ API تا پاسخ، مدل را دوباره فراخوانی نکند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T007 — کنترل‌کنندهٔ مرحله‌ای عمومی

- فاز: **F1**
- وابستگی: T004، T005، T006، T002؛ هدف‌ها: REQ-103، REQ-106
- دامنه: وصل‌کردن ProjectBook، دستیار، عامل، ارزیاب و تحویل در یک مسیر؛ ۶ یا بیشتر مرحله.
- فایل‌های هدف: `src/csef_gate/workflow/engine.py`، `src/csef_gate/workflow/stages.py`، `src/csef_gate/workflow/handoffs.py`، `src/csef_gate/interfaces/cli.py`
- آزمون پیشنهادی: `tests/integration/test_chat_to_handoff.py`
- معیار پایان: از گفتگوی نمونه تا یک برش کامل، بدون دستکاری دستی پایگاه اجرا شود؛ هیچ مرحلهٔ وابسته از خروجی نامعتبر استفاده نکند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T008 — ادامه پس از قطع و ابطال وابستگی‌ها

- فاز: **F1**
- وابستگی: T007؛ هدف‌ها: REQ-104، REQ-106
- دامنه: resume، شمارش تلاش پایدار، invalidation و آشتی نتیجهٔ نامعلوم.
- فایل‌های هدف: `src/csef_gate/lifecycle/change_control.py`، `src/csef_gate/workflow/recovery.py`
- آزمون پیشنهادی: `tests/integration/test_resume_boundaries.py`
- معیار پایان: در نقاط قبل/بعد از مدل، patch، تست و تحویل قطع شود؛ ادامه بدون پذیرش کهنه و بدون تکرار عملیات غیرقابل‌برگشت باشد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T009 — ایندکس سبک مخزن و تازگی دانش

- فاز: **F2**
- وابستگی: T005؛ هدف‌ها: REQ-101، REQ-104
- دامنه: مسیر/هش/نشانه‌ها/ماژول‌ها و SQLite FTS5؛ بدون پایگاه برداری اجباری.
- فایل‌های هدف: `src/csef_gate/context/index.py`، `src/csef_gate/context/retrieval.py`
- آزمون پیشنهادی: `tests/context/test_index_freshness.py`
- معیار پایان: پس از تغییر فایل یا شاخه، سند/خلاصهٔ کهنه شناسایی شود؛ فایل حذف‌شده به‌عنوان واقعیت جاری بازیابی نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T010 — بستهٔ زمینه و ردیابی هدف تا آزمون

- فاز: **F2**
- وابستگی: T009، T007؛ هدف‌ها: REQ-101، REQ-104، REQ-106
- دامنه: facts اجباری، کد مرتبط، اسناد مرتبط، فهرست موارد حذف‌شده و requirement trace.
- فایل‌های هدف: `src/csef_gate/context/packets.py`، `src/csef_gate/context/traceability.py`
- آزمون پیشنهادی: `tests/context/test_goal_preservation.py`
- معیار پایان: سقف زمینه هدف حیاتی را نبرد؛ منبع هر ادعا قابل بازیابی باشد؛ حذف اطلاعات صریح و قابل جبران باشد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T011 — مصاحبهٔ مهندسی و پیش‌فرض‌های کم‌اصطکاک

- فاز: **F2**
- وابستگی: T006، T010؛ هدف‌ها: REQ-103، REQ-105
- دامنه: ترجمهٔ هدف طبیعی به مسئله، سناریو، معیار موفقیت و مجهول‌های مؤثر.
- فایل‌های هدف: `src/csef_gate/engineering/interview.py`، `templates/brief.md`، `templates/questions.md`
- آزمون پیشنهادی: `tests/engineering/test_interview_cases.py`
- معیار پایان: در موارد متناقض، سؤال لازم و دلیل آن تولید شود؛ انتخاب پوشه/فریم‌ورک بی‌دلیل به کاربر واگذار نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T012 — معماری، قرارداد و برنامهٔ برش‌های عمودی

- فاز: **F2**
- وابستگی: T011، T002؛ هدف‌ها: REQ-105، REQ-106
- دامنه: ADR، مالکیت داده، گزینه‌های ردشده، NFR، قرارداد و ترتیب ساخت قابل تطبیق.
- فایل‌های هدف: `src/csef_gate/engineering/architecture.py`، `src/csef_gate/engineering/planning.py`، `src/csef_gate/engineering/templates.py`، `templates/adr.md`، `templates/contracts.md`، `templates/task.md`، `templates/handoff.md`، `templates/release.md`
- آزمون پیشنهادی: `tests/engineering/test_architecture_scenarios.py`
- معیار پایان: معماری با سناریو و محدودیت مرتبط باشد؛ وابستگی‌ها و معیار هر برش روشن باشند؛ مدل صرفاً با ذکر شناسه‌ها امتیاز کیفیت نگیرد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T013 — پروتکل مدل و استخراج آداپتر Codex

- فاز: **F3**
- وابستگی: T003؛ هدف‌ها: REQ-101، REQ-102
- دامنه: یکسان‌کردن دو مسیر مدل فعلی؛ جداکردن ModelProvider از CodingAgent.
- فایل‌های هدف: `src/csef_gate/providers/base.py`، `src/csef_gate/providers/codex_cli.py`
- آزمون پیشنهادی: `tests/providers/test_codex_contract.py`
- معیار پایان: receipt یکسان و budget intent برای همهٔ نقش‌ها؛ تنظیم ورود/فایل کاربر بدون اجازه تغییر نکند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T014 — قابلیت و سلامت فراهم‌کننده

- فاز: **F3**
- وابستگی: T013؛ هدف‌ها: REQ-102، REQ-107
- دامنه: capability probe، timeout، خطاهای نوع‌دار، health و circuit breaker.
- فایل‌های هدف: `src/csef_gate/providers/registry.py`، `src/csef_gate/providers/health.py`
- آزمون پیشنهادی: `tests/providers/test_capability_failures.py`
- معیار پایان: JSON/schema/اندازهٔ زمینه/لغو/usage هر مسیر با درخواست کوچک تأیید شود؛ اختلال باعث حلقهٔ retry نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T015 — درگاه OpenAI-compatible و AvalAI

- فاز: **F3**
- وابستگی: T014؛ هدف‌ها: REQ-101، REQ-102
- دامنه: آداپتر SDK رسمی با endpoint صریح و آزمون Responses/Chat به‌صورت جدا.
- فایل‌های هدف: `src/csef_gate/providers/openai_compatible.py`، `src/csef_gate/providers/secrets.py`
- آزمون پیشنهادی: `tests/providers/test_compatible_routes.py`
- معیار پایان: هیچ درخواست به endpoint اشتباه نرود؛ مدل ناسازگار به‌جای ادعای موفقیت غیرفعال شود؛ کلید به کد تولیدی نرسد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T016 — بودجه، قیمت، انتخاب نقش و failover

- فاز: **F3**
- وابستگی: T014، T015؛ هدف‌ها: REQ-101، REQ-102، REQ-107
- دامنه: reserve/settle، قیمت نسخه‌دار، cache usage و fallback هم‌سطح با سیاست داده.
- فایل‌های هدف: `src/csef_gate/providers/router.py`، `src/csef_gate/providers/usage.py`، `src/csef_gate/providers/pricing.py`، `config/providers.example.toml`، `config/budgets.example.toml`
- آزمون پیشنهادی: `tests/providers/test_budget_and_fallback.py`
- معیار پایان: هزینهٔ نامعلوم صفر حساب نشود؛ سقف/تلاش/مهلت پایدار باشند؛ fallback گران‌تر یا خارج از سیاست بی‌صدا رخ ندهد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T017 — آزمایش مدل محلی Ollama

- فاز: **F3**
- وابستگی: T014، T016؛ هدف‌ها: REQ-101، REQ-102
- دامنه: نمونهٔ محدود محلی و اندازه‌گیری توان حافظه، کیفیت، مصرف و تأخیر.
- فایل‌های هدف: `src/csef_gate/providers/ollama.py`
- آزمون پیشنهادی: `tests/providers/test_ollama_offline.py`
- معیار پایان: با اینترنت قطع و مدلِ از قبل موجود، درخواست واقعی انجام شود؛ کیفیت نقش مستقل سنجیده شود؛ ضعیف‌بودن مدل با local بودن پنهان نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T018 — پیشنهاد تغییر نسخه‌بسته و اعمال محدود

- فاز: **F4**
- وابستگی: T007، T010، T013؛ هدف‌ها: REQ-104، REQ-105
- دامنه: proposal با base revision، مسیرهای مجاز، حذف/جابجایی صریح و diff.
- فایل‌های هدف: `src/csef_gate/coding/base.py`، `src/csef_gate/coding/codex.py`، `src/csef_gate/coding/proposals.py`، `src/csef_gate/coding/scope.py`، `src/csef_gate/coding/apply.py`
- آزمون پیشنهادی: `tests/coding/test_revision_and_scope.py`
- معیار پایان: patch برای نسخهٔ دیگر یا خارج از محدوده رد شود؛ تست/بودجه/سیاست پذیرش توسط عامل قابل تضعیف نباشند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T019 — Git workspace، worktree و بازگشت

- فاز: **F4**
- وابستگی: T018؛ هدف‌ها: REQ-104، REQ-106
- دامنه: کار روی شاخه/نسخهٔ جدا، diff قابل بازبینی و حفظ تغییرات موجود کاربر.
- فایل‌های هدف: `src/csef_gate/workspace/git.py`، `src/csef_gate/workspace/snapshots.py`
- آزمون پیشنهادی: `tests/workspace/test_dirty_worktree_recovery.py`
- معیار پایان: پروژهٔ dirty بی‌صدا پاک نشود؛ rollback فقط نسخهٔ تحت مالکیت اجرا را تغییر دهد؛ نام شاخه/commit به شواهد وصل شود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T020 — تحلیل اثر و اتصال عامل جایگزین

- فاز: **F4**
- وابستگی: T018، T019، T016؛ هدف‌ها: REQ-102، REQ-104
- دامنه: impact graph و spike آداپتر Aider؛ مسیر import پیشنهاد از عامل بیرونی حفظ شود.
- فایل‌های هدف: `src/csef_gate/coding/impact.py`، `src/csef_gate/coding/aider.py`
- آزمون پیشنهادی: `tests/integrations/test_alternative_agent.py`
- معیار پایان: هیچ عامل جایگزین مستقیم در کنترل‌پلین ننویسد؛ با عوض‌شدن عامل، هدف و oracle ثابت بمانند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T021 — قرارداد محیط اجرا و پروفایل تهدید

- فاز: **F5**
- وابستگی: T003، T018؛ هدف‌ها: REQ-104، REQ-105
- دامنه: ExecutionProvider، محدودیت منبع، تفکیک شبکهٔ مهمان و میزبان، lifecycle محیط.
- فایل‌های هدف: `src/csef_gate/execution/base.py`، `src/csef_gate/execution/native.py`، `src/csef_gate/execution/profiles.py`، `profiles/execution/guest-default.json`
- آزمون پیشنهادی: `tests/execution/test_profile_contract.py`
- معیار پایان: برنامهٔ وب بتواند loopback مهمان داشته باشد ولی میزبان/اسرار در دسترس نباشند؛ نبود قابلیت باعث توقف شود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T022 — محیط VM اختصاصی و مدیریت اتصال

- فاز: **F5**
- وابستگی: T021؛ هدف‌ها: REQ-105، REQ-106
- دامنه: پروفایل Hyper-V و Linux guest، اتصال مدیریتی محدود و image digest.
- فایل‌های هدف: `src/csef_gate/execution/hyperv.py`، `src/csef_gate/execution/ssh_guest.py`، `scripts/vm/provision.ps1`، `scripts/vm/guest-bootstrap.sh`
- آزمون پیشنهادی: `tests/system/test_guest_boundary.py`
- معیار پایان: کد مهمان به فایل/سرویس میزبان و DB کنترل نرسد؛ مسیر تست فایل، شبکه، resource و پاک‌سازی خروجی‌ها ثبت شود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T023 — انتقال ورودی و خروجی مجاز

- فاز: **F5**
- وابستگی: T022؛ هدف‌ها: REQ-104، REQ-105
- دامنه: manifest محتوا، انتقال امن فایل، مقابله با traversal/reparse/archive bomb.
- فایل‌های هدف: `src/csef_gate/execution/transfer.py`
- آزمون پیشنهادی: `tests/execution/test_transfer_adversarial.py`
- معیار پایان: فایل خارج از allowlist، symlink و خروجی بیش از سقف رد شوند؛ digest منبع اجراشده با پیشنهاد یکی باشد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T024 — probes واقعی و بازیابی محیط

- فاز: **F5**
- وابستگی: T022، T023؛ هدف‌ها: REQ-105، REQ-106
- دامنه: آزمون escape محدود، دسترسی میزبان، قطع SSH، process tree و reset محیط.
- فایل‌های هدف: `src/csef_gate/execution/probes.py`
- آزمون پیشنهادی: `tests/system/test_environment_recovery.py`
- معیار پایان: مرزهای ادعاشده با positive/negative control سنجیده شوند؛ قطع ارتباط UNKNOWN بدهد و به PASS تبدیل نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T025 — طرح و اجرای ارزیابی Python

- فاز: **F6**
- وابستگی: T018، T021؛ هدف‌ها: REQ-105، REQ-106
- دامنه: criterion typed، parser خروجی، pytest/Ruff/mypy در محیط مجاز.
- فایل‌های هدف: `src/csef_gate/verification/plan.py`، `src/csef_gate/verification/runner.py`، `src/csef_gate/verification/python_pack.py`
- آزمون پیشنهادی: `tests/verification/test_report_failure_modes.py`
- معیار پایان: exit صفر با تست خالی/skip حیاتی/گزارش جعلی قبول نشود؛ همهٔ معیارهای لازم outcome داشته باشند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T026 — قواعد معماری و پذیرش مستقل

- فاز: **F6**
- وابستگی: T010، T012، T025؛ هدف‌ها: REQ-104، REQ-105، REQ-107
- دامنه: dependency rules، تست رگرسیون، holdout و بررسی traceability.
- فایل‌های هدف: `src/csef_gate/verification/architecture.py`، `src/csef_gate/verification/security.py`، `config/architecture-rules.example.json`
- آزمون پیشنهادی: `tests/verification/test_architecture_regressions.py`
- معیار پایان: تخلف لایه، حذف نیاز حیاتی و migration مخرب کشف شوند؛ صحت معماری با AST صرف اعلام نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T027 — اختیار تأیید و checkpoint واقعی

- فاز: **F6**
- وابستگی: T004، T008، T024، T025؛ هدف‌ها: REQ-104، REQ-106
- دامنه: verify-and-promote اتمیک با رکورد کنترل‌کننده؛ بدون permit قابل جعل.
- فایل‌های هدف: `src/csef_gate/verification/verdict.py`، `src/csef_gate/verification/authority.py`
- آزمون پیشنهادی: `tests/verification/test_forged_authority.py`
- معیار پایان: گزارش/هش/ورودی PASS ساختگی، replay، نسخهٔ متفاوت و نتیجهٔ UNKNOWN نتوانند تأیید بگیرند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T028 — بازبین دوم با سیاست ریسک و سؤال ضروری

- فاز: **F6**
- وابستگی: T010، T016، T026؛ هدف‌ها: REQ-101، REQ-103، REQ-107
- دامنه: severity و دلیل، ارجاع به fact/source، ثبت dissent و مسیر سؤال انسانی.
- فایل‌های هدف: `src/csef_gate/reviewing/policy.py`، `src/csef_gate/reviewing/semantic.py`، `src/csef_gate/reviewing/findings.py`
- آزمون پیشنهادی: `tests/reviewing/test_risk_and_dissent.py`
- معیار پایان: اختلاف بازبین خودکار به رأی‌گیری یا تأیید تبدیل نشود؛ بررسی ماشینی در حالت بدون مدل هم باقی بماند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T029 — اتصال همین چت از طریق MCP

- فاز: **F7**
- وابستگی: T007، T011، T028؛ هدف‌ها: REQ-102، REQ-103
- دامنه: ابزارهای پروژه/پرسش/پیشرفت/اجرا/گزارش با SDK رسمی MCP.
- فایل‌های هدف: `src/csef_gate/interfaces/mcp.py`، `examples/mcp/client-configuration.example.json`
- آزمون پیشنهادی: `tests/interfaces/test_mcp_client_contract.py`
- معیار پایان: دو مشتری پشتیبانی‌شده روی نسخهٔ قفل‌شده آزمایش شوند؛ tool خام shell وجود نداشته باشد؛ نوشتن بدون scope ممنوع باشد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T030 — API محلی و رابط سادهٔ اختیاری

- فاز: **F7**
- وابستگی: T029؛ هدف‌ها: REQ-103
- دامنه: فقط اگر مسیر چت کافی نبود: FastAPI و صفحهٔ گفتگوی ساده با همان سرویس‌ها.
- فایل‌های هدف: `src/csef_gate/interfaces/api.py`، `ui/index.html`، `ui/chat.js`، `ui/styles.css`
- آزمون پیشنهادی: `tests/interfaces/test_local_api_authority.py`
- معیار پایان: کاربر بدون ترمینال هدف/پاسخ/توقف/خروجی را مدیریت کند؛ مجوزها در API و MCP یکسان بمانند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T031 — GitHub read-only و PR محدود

- فاز: **F7**
- وابستگی: T019، T027؛ هدف‌ها: REQ-102، REQ-106
- دامنه: خواندن repo/issue/CI، سپس PR draft فقط در scope صریح کاربر.
- فایل‌های هدف: `src/csef_gate/workspace/github.py`
- آزمون پیشنهادی: `tests/workspace/test_remote_scope.py`
- معیار پایان: شاخهٔ اشتباه/مجوز ناکافی/تغییر diff، عملیات انتشار را متوقف کنند؛ merge/deploy خودکار پیش‌فرض نباشد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T032 — بستهٔ تحویل، backup و restore

- فاز: **F8**
- وابستگی: T027، T031؛ هدف‌ها: REQ-105، REQ-106
- دامنه: ZIP/نسخهٔ Git، راهنمای نصب، lock، محدودیت‌ها و backup قابل بازیابی.
- فایل‌های هدف: `src/csef_gate/delivery/bundle.py`، `src/csef_gate/delivery/backup.py`، `src/csef_gate/delivery/restore.py`، `docs/RUNBOOK.fa.md`، `docs/BACKUP-RESTORE.fa.md`
- آزمون پیشنهادی: `tests/delivery/test_clean_install_and_restore.py`
- معیار پایان: نصب در محیط تمیز و بازگردانی پروژه+DB+artifact آزمایش شود؛ اسرار و دادهٔ واقعی وارد بسته نشوند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T033 — قالب پروژه‌های API و وب و Playwright

- فاز: **F8**
- وابستگی: T022، T025، T026؛ هدف‌ها: REQ-105
- دامنه: افزودن فقط دو خانوادهٔ بعدی: Python API و وب کوچک JS/TS؛ browser tests در مهمان.
- فایل‌های هدف: `src/csef_gate/verification/web_pack.py`
- آزمون پیشنهادی: `tests/system/test_web_journey.py`
- معیار پایان: مسیر واقعی کاربر، داده و ارتقا سنجیده شوند؛ قالب‌ها به محصول CLI تحمیل نشوند؛ مدلِ صرفاً ظاهر‌ساز قبول نشود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T034 — گزارش، حفظ حریم داده و نگهداری لاگ

- فاز: **F8**
- وابستگی: T004، T016؛ هدف‌ها: REQ-101، REQ-103
- دامنه: رویداد قابل فهم، redaction، retention و مشاهدهٔ جزئیات اختیاری.
- فایل‌های هدف: `src/csef_gate/observability/events.py`، `src/csef_gate/observability/redaction.py`
- آزمون پیشنهادی: `tests/observability/test_redaction_and_retention.py`
- معیار پایان: کلید/متن حساس پیش‌فرض در لاگ نباشد؛ مصرف و زمان و تصمیم رد/قبول قابل دنبال‌کردن باشند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T035 — مقایسهٔ منصفانه روی پروژه‌های متفاوت

- فاز: **F9**
- وابستگی: T028، T032، T033، T034؛ هدف‌ها: REQ-101، REQ-103، REQ-104، REQ-105
- دامنه: direct agent در برابر CSEF هدفمند؛ دادهٔ جدا، تکرار جفتی و دخالت واقعی کاربر.
- فایل‌های هدف: `src/csef_gate/evaluation/corpus.py`، `src/csef_gate/evaluation/runner.py`، `src/csef_gate/evaluation/metrics.py`، `experiments/corpus/manifest.json`، `experiments/protocol-vnext.json`
- آزمون پیشنهادی: `tests/evaluation/test_frozen_protocol.py`
- معیار پایان: هزینهٔ واقعی/واحدنامعلوم، زمان فعال کاربر، باگ تحویل و توقف نابجا گزارش شوند؛ نتیجهٔ منفی هم منتشر شود.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T036 — بستهٔ نصب و CI پروژهٔ CSEF

- فاز: **F9**
- وابستگی: T003، T027، T029، T035؛ هدف‌ها: REQ-102، REQ-103، REQ-106
- دامنه: قفل وابستگی، smoke نصب، migration، offline state و artifact انتشار.
- فایل‌های هدف: `uv.lock`، `.github/workflows/ci.yml`، `scripts/install.ps1`، `scripts/install.sh`، `THIRD_PARTY_NOTICES.md`
- آزمون پیشنهادی: `tests/system/test_package_smoke.py`
- معیار پایان: نصب روی ماشین تمیز، اجرای نمونه، resume و uninstall بدون از بین بردن پروژهٔ کاربر تأیید شوند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T037 — آزمایش LiteLLM پس از نیاز چنددرگاهی

- فاز: **LATER**
- وابستگی: T016، T035؛ هدف‌ها: REQ-101، REQ-102
- دامنه: فقط اگر درگاه سبک نگهداری‌پذیر نبود: SDK/Proxy پشت همان interface.
- فایل‌های هدف: `src/csef_gate/integrations/litellm.py`
- آزمون پیشنهادی: `tests/integrations/test_litellm_route_parity.py`
- معیار پایان: فایدهٔ اقتصادی و بار عملیاتی مقایسه و اجزای دارای مجوز متفاوت تفکیک شوند؛ gateway اختیار تأیید نگیرد.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## T038 — آزمایش OpenHands SDK و بازیابی چندزبانه

- فاز: **LATER**
- وابستگی: T020، T035؛ هدف‌ها: REQ-102، REQ-105
- دامنه: آداپتر SDK و tree-sitter فقط با نیاز اثبات‌شدهٔ مخزن بزرگ/چندزبانه.
- فایل‌های هدف: `src/csef_gate/integrations/openhands.py`
- آزمون پیشنهادی: `tests/integrations/test_openhands_contract.py`
- معیار پایان: با معیار یکسان از مسیر ساده بهتر باشد؛ failure و provenance همان قرارداد کنترل را رعایت کنند.
- شاهد لازم: نسخهٔ ورودی و کد، فرمان/روش مشاهده، outcome، artifact واقعی و محدودیت باقی‌مانده. سبزشدن یک تست تکرارکنندهٔ کد کافی نیست.

## قرارداد انجام هر task

قبل از اجرا: input و revision، scope، budget، oracle و خطر مشخص شوند. حین اجرا: تغییر محدود، ثبت intent و شواهد. پایان: خروجی قابل بازبینی، تست متناسب و اثر بر اسناد/نیازها. کار بسته نمی‌شود اگر بخش اجباری آن فقط PROPOSED مانده باشد. فایل JSON همراه یک backlog داده‌ای است و هنوز scheduler فعلی آن را خودکار اجرا نمی‌کند.
