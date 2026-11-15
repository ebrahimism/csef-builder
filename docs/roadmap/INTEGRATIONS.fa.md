# اتصال‌ها و پروژه‌های گیت‌هاب

تاریخ بررسی: ۱۵ نوامبر ۲۰۲۶. وضعیت repository و بعضی README/اسناد رسمی به‌صورت read-only بررسی شده‌اند. این بررسی نصب، آزمون امنیت، تأیید کیفیت مدل یا تست یکپارچه‌سازی نیست. آداپتر Codex و runner فعلی pytest فقط در نمونهٔ محدود اجرا شده‌اند؛ بقیه عمدتاً پیشنهاد آینده‌اند.

## فهرست انتخاب و عدم انتخاب

ستون مجوز، شناسهٔ گزارش‌شده در API گیت‌هاب است؛ جای بررسی LICENSE/NOTICE اجزای دقیق در نسخهٔ قفل‌شده را نمی‌گیرد. NOASSERTION به معنی «بدون مجوز» نیست؛ یعنی طبقه‌بندی خودکار قطعی نبوده است.

| پروژه | نقش | وضعیت انتخاب | شناسهٔ مجوز گزارش‌شده | کار |
| --- | --- | --- | --- | --- |
| [openai/codex](https://github.com/openai/codex) | عامل کدنویسی اصلی با CLI نصب‌شده | موجود؛ توسعهٔ آداپتر | Apache-2.0 | T013، T018 |
| [github/spec-kit](https://github.com/github/spec-kit) | قالب، import/export و workflow/extension محدود | آزمایش اجباری پیش از گسترش orchestration | MIT | T002، T012 |
| [pydantic/pydantic](https://github.com/pydantic/pydantic) | schemaهای ورودی/خروجی نسخه‌دار | وابستگی موجود؛ توسعهٔ استفاده | MIT | T003 |
| [openai/openai-python](https://github.com/openai/openai-python) | کلاینت API سازگار با endpoint صریح | انتخاب برای آداپتر مستقیم | Apache-2.0 | T015 |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | اتصال همین چت و ابزارهای محدود | انتخاب مشروط به آزمون کلاینت | MIT | T029 |
| [git/git](https://github.com/git/git) | workspace، worktree، diff و snapshot | استفاده از CLI؛ نه کپی کد | NOASSERTION | T019 |
| [astral-sh/uv](https://github.com/astral-sh/uv) | محیط تکرارپذیر، lock و نصب ابزار | انتخاب برای بسته‌بندی Python | Apache-2.0 | T036 |
| [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | آزمون رفتاری و رگرسیون | موجود در آزمون‌ها؛ توسعهٔ runner | MIT | T025 |
| [astral-sh/ruff](https://github.com/astral-sh/ruff) | lint و قواعد سبک/خطای مشخص | انتخاب برای Python pack | MIT | T025 |
| [python/mypy](https://github.com/python/mypy) | type checking انتخاب‌شده در قرارداد پروژه | انتخاب برای Python pack | NOASSERTION | T025 |
| [ollama/ollama](https://github.com/ollama/ollama) | مدل محلی برای نقش‌های مناسب | آزمایش محلی؛ نه تضمین صرفه | MIT | T017 |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | کدنویسی پشت CodingAgent مستقل | عامل جایگزین پس از spike | Apache-2.0 | T020 |
| [microsoft/playwright](https://github.com/microsoft/playwright) | آزمون مسیر کاربر و مرورگر داخل guest | وقتی پروژهٔ هدف وب است | Apache-2.0 | T033 |
| [fastapi/fastapi](https://github.com/fastapi/fastapi) | سرویس محلی روی application service مشترک | مشروط؛ API نمونه و UI محلی بعدی | MIT | T030، T033 |
| [docker/cli](https://github.com/docker/cli) | محیط ابزار/وابستگی در مهمان | اختیاری درون VM | Apache-2.0 | T022 |
| [moby/moby](https://github.com/moby/moby) | runtime کانتینر داخل مرز VM | اختیاری درون VM | Apache-2.0 | T022 |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | gateway/router پشت ModelProvider | بعداً و فقط با نیاز اندازه‌گیری‌شده | NOASSERTION | T037 |
| [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk) | آداپتر SDK عامل/سرور | بعداً و مشروط به برتری آزمایش | MIT | T038 |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | رابط/Canvas آماده برای بررسی به‌جای ساخت UI اضافه | مرجع مقایسه؛ نه وابستگی هسته | MIT | T038 |
| [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) | ایندکس نماد/وابستگی چند زبان | بعد از نیاز واقعی چندزبانه | MIT | T038 |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | گزینهٔ جایگزین موتور گردش‌کار | در v1 انتخاب نشده | MIT | T007 |
| [temporalio/temporal](https://github.com/temporalio/temporal) | گزینهٔ آینده برای گردش‌کار توزیع‌شده | در v1 انتخاب نشده | MIT | T008 |
| [jdx/mise](https://github.com/jdx/mise) | گزینهٔ آیندهٔ مدیریت toolchain چندزبانه | در v1 انتخاب نشده | MIT | T033 |
| [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) | کشف اسرار در diff و بستهٔ تحویل | انتخاب برای بررسی کیفیت؛ پس از قفل نسخه | MIT | T026 |
| [pypa/pip-audit](https://github.com/pypa/pip-audit) | بررسی آسیب‌پذیری‌های شناخته‌شدهٔ وابستگی Python | انتخاب برای بررسی کیفیت؛ پس از قفل نسخه | Apache-2.0 | T026 |

## ۱. Codex: عامل موجود و مسیر اولیه

منبع: [openai/codex](https://github.com/openai/codex) و [اجرای non-interactive](https://learn.chatgpt.com/docs/non-interactive-mode).

اتصال فعلی CLI است. کد بعدی دو فراخوانی مشابه در backends/model_session را به یک transport منتقل می‌کند. coding/codex کار را به پیشنهاد محدود تبدیل می‌کند؛ کنترل‌کننده source scope و oracle و outcome را نگه می‌دارد.

آزمون اتصال: JSON مطابق schema، خروج نامعتبر، مهلت، output بیش از سقف، لغو، قطع قبل/بعد از پاسخ، usage ناقص و تغییر نسخهٔ CLI. دادهٔ source فقط در scope انتخاب‌شده فرستاده شود. تنظیم ورود و فایل config اصلی کاربر بازنویسی نشود.

ورود ChatGPT در CLI، مجوز یا اعتبار API برای SDK مستقیم محسوب نمی‌شود. مسیر API به credential و مجوز خودش نیاز دارد.

## ۲. Spec Kit: استفادهٔ مجدد پیش از گسترش موتور

منابع: [README](https://github.com/github/spec-kit)، [workflow](https://github.github.io/spec-kit/workflows/overview.html)، [extension](https://github.github.io/spec-kit/extensions/overview.html)، [spec template](https://github.com/github/spec-kit/blob/main/templates/spec-template.md)، [task template](https://github.com/github/spec-kit/blob/main/templates/tasks-template.md).

وضعیت فعلی آن فراتر از چند فایل template است: workflow قابل ادامه، gate بازبینی و extension دارد. قبل از ساخت orchestration بیشتر باید نمونهٔ محدود آن آزمایش شود.

روش اتصال پیشنهادی:
۱. export نیازهای پذیرفتهٔ CSEF با شناسه و منشأ به قالب spec/plan/tasks.
۲. import خروجی به‌عنوان پیشنهاد؛ شناسه‌ها و ارتباط‌ها نباید گم شوند.
۳. extension/step محدود، درخواست ارزیابی را به سرویس CSEF بدهد.
۴. gate و وضعیت خود ابزار، منبع اختیار انتشار CSEF نشوند.
۵. stepهای shell فقط از مسیر ExecutionProvider مجاز عبور کنند؛ catalog یا workflow نصب‌شده مجوز ضمنی shell نیست.

دو تفاوت مهم: template فعلی task، آزمون را همه‌جا الزامی نمی‌کند؛ preset CSEF باید معیار اجباری کارهای لازم را روشن کند. همچنین resume ابزار، به‌تنهایی exactly-once برای اثر خارجی نمی‌دهد؛ نتیجهٔ نامعلوم در کنترل‌کننده reconcile می‌شود.

معیار تصمیم T002: round-trip شناسه/نیاز/ADR، حفظ override، سازگاری integration عامل، resume، scope و هزینه. اگر native workflow برای state مناسب نبود، از قالب و process آن استفاده می‌کنیم و state اختیار را در CSEF نگه می‌داریم. دو منبع حقیقتِ رقابت‌کننده ایجاد نمی‌شود. استفاده از کل ابزار پیشاپیش قطعی نیست.

## ۳. SDK رسمی و AvalAI: مسیر جایگزین دسترسی

منابع: [openai/openai-python](https://github.com/openai/openai-python)، [API AvalAI](https://docs.avalai.org/en/api-reference/introduction)، [کتابخانه‌ها](https://docs.avalai.org/en/libraries)، [Codex و تفاوت endpointها](https://docs.avalai.org/en/guides/setup-codex).

لایهٔ providers/openai_compatible قرارداد ModelRequest را با endpoint و credential مشخص ارسال می‌کند؛ Responses و Chat دو مسیر جدا با capability probe هستند. base URL مستند AvalAI برابر `https://api.avalai.ir/v1` است. نام مدل، کلید، قیمت و محدودیت‌ها تنظیمات صاحب پروژه‌اند.

تست لازم: مقصد واقعی درخواست، schema، سقف output، usage، خطا، streaming در صورت استفاده، cancellation و timeout. سازگاری OpenAI-format با سازگاری کامل همهٔ model routeها یکی نیست. این SDK یک عامل کدنویسی یا sandbox جدید تولید نمی‌کند.

## ۴. Ollama: گزینهٔ محلی با آزمون نقش

منابع: [ollama/ollama](https://github.com/ollama/ollama)، [structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

برای مدل محلیِ از قبل موجود، endpoint محلی و JSON/schema آزمایش می‌شود. دستگاه، RAM/VRAM، مدل، quantization، context و latency در receipt/benchmark مشخص باشند. دانلود مدل و انتقال داده اقدام جدا با سیاست شبکه است.

هدف اولیه: نقش مناسب و محدود مثل طبقه‌بندی سؤال یا بازبینی ساده؛ نقش سخت معماری/کدنویسی فقط پس از مقایسه. مدل محلیِ ضعیف فقط به‌خاطر نداشتن صورت‌حساب API انتخاب نمی‌شود. cloud و local یک سطح capability فرض نمی‌شوند؛ اسناد فعلی دربارهٔ محدودیت structured output در cloud هشدار دارند.

## ۵. Aider: CodingAgent جایگزین

منبع: [Aider-AI/aider](https://github.com/Aider-AI/aider).

Adapter در candidate/worktree متعلق به اجرا یا guest کار می‌کند و diff را به ChangeProposal برمی‌گرداند. رفتار auto-commit و اجرای lint/test در نسخهٔ انتخابی بررسی می‌شود؛ commit آن وارد main یا history معتبر پروژه نمی‌شود مگر gate کنترل‌کننده عبور کرده باشد.

معیار spike: قابلیت مدل انتخابی، اختلافِ قابل‌اعمال به base دقیق، هزینه، لغو و عدم دسترسی به oracle/اسرار/DB. نتیجهٔ test خود عامل، شاهد تکمیلی است؛ مرجع نهایی ارزیابی نیست. این گزینه فعلاً جایگزین فعال محسوب نمی‌شود.

## ۶. MCP: همان چت، بدون ترمینال اجباری برای کاربر

منبع: [SDK رسمی Python](https://github.com/modelcontextprotocol/python-sdk).

شاخهٔ فعلی SDK مستندات v2 و API جدید دارد. نام class و transport از نسخهٔ قفل‌شده گرفته می‌شود؛ مثال‌های قدیمی FastMCP کورکورانه کپی نمی‌شوند. stdio برای نمونهٔ محلی و Streamable HTTP برای مسیر لازمِ پشتیبانی‌شده بررسی شوند.

ابزارهای مجاز روی سرویس مشترک: create/read project، پیام، سؤال/پاسخ، plan/context، اجرای مرحله، توقف، diff، review، report و artifact مجاز. ابزار arbitrary shell/path در interface عادی وجود نداشته باشد.

معیار اتصال: schema و annotation درست، auth/scope مستقل از prompt، replay، expected revision، دو میزبان واقعی، interruption و نمایش فایل. امکان اتصال به هر حساب یا هر محصول ChatGPT از وجود SDK نتیجه نمی‌شود؛ قابلیت همان میزبان باید بررسی شود.

## ۷. Git و GitHub

منابع: [git/git](https://github.com/git/git) و [GitHub REST docs](https://docs.github.com/en/rest).

Git CLI برای snapshot، worktree و diff کافی است. کد Git کپی نمی‌شود. repository کاربر باید صریح انتخاب شود؛ GitHub اتصال اختیاری بالاتر از core محلی است.

مرحلهٔ اول read-only: branch، issue و CI. نوشتن remote در مرحلهٔ بعد با scope صریح، مقصد، branch و digest مشخص. توکن در کنترل‌پلین می‌ماند؛ مدل و کد guest آن را نمی‌گیرند. merge، publish و deploy پیش‌فرض خودکار نیستند.

## ۸. محیط اجرا: Hyper-V و container مهمان

منابع: [Microsoft Hyper-V](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/get-started/Install-Hyper-V)، [moby/moby](https://github.com/moby/moby)، [docker/cli](https://github.com/docker/cli).

Hyper-V محصول مایکروسافت است، نه dependency Python یا مخزن متن‌باز مورد کپی. host capability/منبع/مجوزهای نصب باید مجدداً بررسی شوند. اجرا باید روی guest اختصاصی با network profile مشخص انجام شود. Docker/Moby درون guest اختیاری است و مرز VM را جایگزین نمی‌کند.

نصب Docker Desktop روی میزبان شرط این طرح نیست. شرایط محصول توزیعی و engine/CLI یکسان فرض نمی‌شوند. image، toolchain و lock بعد از آزمون digest می‌گیرند. APIهای مدیریت VM به مدل داده نمی‌شوند؛ کنترل‌کننده فقط scope محیط تحت مالکیت را مدیریت می‌کند.

## ۹. ابزارهای کیفیت

- [pytest](https://github.com/pytest-dev/pytest): رفتار و رگرسیون؛ parser گزارش باید empty/skip/error را از pass جدا کند.
- [Ruff](https://github.com/astral-sh/ruff): lint/format متناسب؛ اصلاح سبک نباید باگ یا تغییر scope را پنهان کند.
- [mypy](https://github.com/python/mypy): نوع‌ها در خانوادهٔ Python؛ LICENSE ریشه اجزای MIT و قسمت‌های دیگر را توضیح می‌دهد.
- [Playwright](https://github.com/microsoft/playwright): مسیر واقعی مرورگر برای پروژهٔ وب؛ داخل guest و با artifact محدود.
- [Gitleaks](https://github.com/gitleaks/gitleaks): بررسی diff/بسته برای اسرار.
- [pip-audit](https://github.com/pypa/pip-audit): آسیب‌پذیری شناخته‌شدهٔ وابستگی‌های Python با lock مشخص.
- [Pydantic](https://github.com/pydantic/pydantic): اعتبارسنجی schema؛ جای اختیار/امضا/مجوز نیست.
- [uv](https://github.com/astral-sh/uv): نصب و lock تکرارپذیر Python و ابزارها.

ابزار audit هم نباید روی میزبان، کد setup ناشناخته را برای حل dependency اجرا کند. پروژه در محیط مجاز آماده می‌شود و گزارش استانداردش وارد ارزیاب می‌شود. نبود یافتهٔ scanner به معنی امن‌بودن همهٔ سیستم نیست.

## ۱۰. FastAPI و UI بعدی

منبع: [fastapi/fastapi](https://github.com/fastapi/fastapi).

برای برنامهٔ هدف Python API و در صورت نیاز رابط محلی CSEF مناسب بررسی می‌شود. در core تا قبل از نیاز، server اجباری نیست. اگر رابط مستقل لازم شد، یک صفحهٔ چت ساده با همان application service کافی است؛ frontend framework بزرگ پیش‌نیاز نیست.

authentication، origin، download scope و وضعیت اجرا بین API و MCP یکسان‌اند. وجود localhost به تنهایی احراز هویت نیست. برنامهٔ کاربر و سرور مدیریت CSEF در یک حوزهٔ اختیار قرار نمی‌گیرند.

## ۱۱. LiteLLM: بعد از اثبات نیاز

منابع: [BerriAI/litellm](https://github.com/BerriAI/litellm)، [LICENSE](https://github.com/BerriAI/litellm/blob/main/LICENSE).

نقش احتمالی: gateway/router پشت ModelProvider؛ هزینه و complexity سرویس اضافه باید از آداپتر سبک بهتر باشد. انتخاب آن به معنی فعال‌بودن همهٔ قابلیت‌ها یا کاهش قیمت provider نیست.

LICENSE فعلی محتوای مسیر enterprise را از بخش‌های بیرون آن تفکیک می‌کند؛ گزارش metadata با NOASSERTION نباید به MIT برای همهٔ repository تبدیل شود. نسخه/فایل‌های مورد استفاده جدا ثبت می‌شوند.

## ۱۲. OpenHands SDK و Canvas

منابع: [software-agent-sdk](https://github.com/OpenHands/software-agent-sdk)، [OpenHands](https://github.com/OpenHands/OpenHands).

اگر نیاز agent backend پیشرفته‌تر ثابت شد، SDK و Agent Server بررسی می‌شوند. گرفتن TerminalTool/FileEditorTool با workspace میزبان پیش‌فرض، سیاست کنترل ما را برآورده نمی‌کند؛ ابزارها باید به guest و scope مجاز وصل شوند.

OpenHands UI/Canvas یک محصول کامل دیگر است و SDK جزء متفاوتی است. UI آماده فقط اگر از ساخت دوبارهٔ رابط به‌صرفه‌تر بود انتخاب می‌شود. ایزوله‌کردن اجرای conversation را با ایزوله‌کردن کل سرویس و کنترل‌پلین اشتباه نمی‌گیریم.

## ۱۳. گزینه‌های فعلاً خارج از core

- [tree-sitter](https://github.com/tree-sitter/tree-sitter): فقط پس از کم‌آوردن ast و جستجوی متن در چند زبان.
- [LangGraph](https://github.com/langchain-ai/langgraph): گزینهٔ motor workflow؛ فعلاً source-of-truth دوم نمی‌سازیم.
- [Temporal](https://github.com/temporalio/temporal): برای مسئلهٔ واقعی workflow توزیع‌شده؛ سرویس اضافی برای pilot شخصی لازم نیست.
- [mise](https://github.com/jdx/mise): toolchain چندزبانه در صورت نیاز؛ uv و image قفل‌شده ابتدا کافی‌اند.

این انتخاب‌ها داوری کلی علیه ابزارها نیستند؛ تصمیم محدود به اندازه، هزینه و نیاز CSEF فعلی‌اند.

## ۱۴. پروتکل پذیرش هر dependency یا integration

۱. هدف و جایگزین ساده‌تر و نسخه مشخص شود. ۲. README/کد/مجوز اجزای لازم بررسی شود. ۳. نصب روی محیط جدا و با lock انجام شود. ۴. حداقل مسیر موفق و شکست/قطع و invalid output آزمایش شوند. ۵. state، budget، credential و اختیار کنترل بررسی شوند. ۶. نتیجه و محدودیت ثبت شود. ۷. فقط پس از این مراحل dependency قفل و در مسیر پیش‌فرض فعال شود.

HEADهای موجود در [repositories.json](repositories.json) snapshot تحقیق‌اند؛ dependency lock و نسخهٔ تأییدشده نیستند. صرف غیرآرشیوی‌بودن یا تعداد ستاره تأیید نگهداری، امنیت یا تناسب نیست.
