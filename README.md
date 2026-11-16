# CSEF — سنجش مستقل برای عامل کدنویسی موجود
# CSEF — Independent Evaluation for an Existing Coding Agent

**CSEF is an independent control and evaluation layer for an existing AI coding agent.**

The installed Codex agent proposes code changes, while a separate evaluator executes the application as a black box and validates its actual behavior against predefined acceptance criteria.

**An agent's claims do not constitute authorization for acceptance.** Approval must be based on independently verified evidence.

The current implementation is a local pilot targeting a Python CLI application built with the standard library. Its primary objective is to demonstrate a complete, real-world feedback loop:

**Detect failure → Request a fix from the existing agent → Apply the proposed changes → Re-evaluate independently.**

---

## 1. Staged Workflow and Project Context

CSEF supports a structured, configurable development lifecycle:

**Problem Discovery → Architecture → Contracts → First End-to-End Slice → Development → Delivery**

The number of stages and their responsibilities are configurable.

Each stage receives:

- A versioned project specification.
- Previously approved decisions.
- Verified deliverables from earlier stages.
- The context required for its assigned responsibilities.

Model-generated suggestions cannot silently modify an approved project specification.

A stage assistant may ask essential clarification questions. Execution remains suspended until the user responds, preventing unnecessary repeated model calls.

### Context Handoff Evaluation

A small-scale comparison evaluated three context-management strategies:

1. **Full History:** Pass the complete conversation history between stages.
2. **Compact Context:** Pass a condensed, structured project context.
3. **Compact Context with Continuous Review:** Use compact context with a persistent reviewer at every stage.

All three strategies passed **25 stage-level behavioral checks**.

Under an identical allocation of design stages:

| Strategy | Input Consumption | Behavioral Checks |
|---|---|---|
| Full History | Baseline | 25 passed |
| Compact Context | 8.68% less than baseline | 25 passed |
| Compact Context + Continuous Reviewer | 52.85% more than compact context alone | 25 passed |

**Important:** These figures represent input consumption, not monetary API costs. They do not establish a quality guarantee for complex production projects.

### Selected Development Direction

The preferred approach combines:

- Persistent, versioned project context.
- Continuous machine-enforced validation.
- Model-based review at architectural decision points and other high-risk checkpoints.
- An optional full-review mode covering every stage.

The quality advantage of targeted review over alternative strategies has not yet been established across diverse projects.

### Documentation and Evidence

- [Operational Workflow and Stage Questions](docs/WORKFLOW.md)
- [Master Implementation Plan, Integrations, and Backlog](docs/MASTER-PLAN.fa.md)
- [Context Handoff Comparison Report](docs/evidence/handoff-screening-2026-11-15/summary.json)
- [Evidence-Based Engineering Decision](docs/decisions/DEC-003-staged-context-and-review.md)
- [Modular Implementation Example](examples/handoff_expenses/README.md)

---

## 2. Installation and Execution

To develop CSEF itself using Codex, consult the following resources:

- [Getting Started and Local Extension Setup](docs/START-CODEX.fa.md)
- [Ready-to-Use Startup Prompt](docs/progress/START-PROMPT.txt)
- [Agent Instructions](AGENTS.md)

The development package tracks implementation progress separately from the proposed roadmap. It does not grant release authorization.

### Prerequisites

Before running the pilot, ensure that:

- Python is installed and available in the terminal.
- Codex CLI is installed.
- Codex authentication is active.
- The control directory is new and located outside the target project directory.

CSEF uses the existing authenticated Codex account. No additional API key is required.

### Initialize the Pilot

From the project root directory in PowerShell:

```powershell
python csef.py init --control 'C:/Users/Kp/Documents/ChatGPT/cffmam/csef-control/my-pilot' --project 'F:/cffmam/examples/expense_cli/project' --spec 'F:/cffmam/examples/expense_cli/acceptance.json'
```

### Run the Evaluation

```powershell
python csef.py run --control 'C:/Users/Kp/Documents/ChatGPT/cffmam/csef-control/my-pilot'
```

The control repository must remain separate from the project being evaluated.

---

## 3. Host Isolation and Security Limitations

### Verified Isolation Properties

Practical isolation tests successfully prevented:

- Reading from the control repository.
- Writing to the control repository.
- Modifying protected executable files.

However, **local TCP connectivity remains possible**.

This is a known limitation of the current host isolation mechanism.

Consequently, the normal execution path reports a `BLOCKED` status and does not create a checkpoint when the required isolation conditions are not satisfied.

### Measurement-Only Mode

For the reviewed local example, CSEF provides a measurement-only execution mode:

```powershell
python csef.py run --control 'C:/Users/Kp/Documents/ChatGPT/cffmam/csef-control/my-pilot' --measure-only
```

This mode:

1. Detects the existing behavioral failures.
2. Requests corrective changes from Codex.
3. Evaluates the proposed changes.
4. Reports the resulting acceptance-test outcomes.

Even when all acceptance criteria pass, the result remains `REVIEW`, with exit code `2`.

**Measurement-only mode never issues a checkpoint.**

This mode is intended exclusively for the reviewed local pilot. It is not suitable for:

- Hostile or untrusted code.
- Security-sensitive projects.
- Production deployment.

Passing behavioral checks must not be interpreted as proof of secure isolation.

---

## 4. Implemented Capabilities

The current CSEF pilot includes the following capabilities.

### 4.1. Independent Control Repository

Project specifications, acceptance tests, and the initial baseline are recorded in a separate control repository.

This separation helps preserve evaluation integrity and prevents the coding agent from directly controlling the acceptance authority.

### 4.2. Restricted Agent Proposals

The coding agent produces structured JSON proposals.

Changes are limited to explicitly authorized file paths.

The agent does not receive unrestricted authority to modify the project or its evaluation criteria.

### 4.3. Black-Box Evaluation

The evaluator does not import application code or application tests into its own process.

Instead, the target application is executed as a separate process.

This preserves the distinction between the evaluator and the software under evaluation.

### 4.4. Operating-System-Level Execution Restrictions

Application execution uses Codex operating-system-level restrictions.

These restrictions provide a degree of isolation, subject to the documented host limitations.

### 4.5. Evidence-Based Acceptance

The evaluator verifies:

- Actual process execution results.
- JSON output.
- Every predefined acceptance criterion.
- Exact file versions.

Acceptance decisions are based on recorded evaluation results rather than the agent's self-reported success.

### 4.6. Controlled Approval Authority

Approval can only be issued from a complete evaluation record stored in the control repository.

Legacy model-based permissions have no authority to approve results in the new evaluation workflow.

### 4.7. Execution Limits and Usage Tracking

The implementation enforces persistent limits on:

- Agent attempts.
- Execution time.

Reported usage is recorded for auditing and analysis.

The system does not claim to provide verified monetary pricing or enforce a dollar-denominated spending limit.

---

## 5. Validation and Test Results

### Real-World Pilot Execution

**Execution date:** November 15, 2026

A fresh pilot run was completed without manual modifications during the evaluation cycle.

The installed Codex agent generated one corrective proposal.

<text></text>

| Metric | Result |
|---|---|
| Initial acceptance criteria passed | 9 |
| Final acceptance criteria passed | 14 of 14 |
| Agent correction proposals | 1 |
| Final evaluation status | `REVIEW` |
| Checkpoint request | Rejected |

The pilot demonstrated a complete failure-detection, agent-correction, and independent re-evaluation cycle.

Despite satisfying all 14 behavioral acceptance criteria, the evaluation remained in `REVIEW` status.

The checkpoint request was rejected, preserving the separation between behavioral correctness and authorization to proceed.

[View Complete Pilot Execution Report](docs/evidence/gate-pilot-2026-11-15/clean-summary.json)

### Repository Test Suite

**133 repository tests passed**, covering:

- Existing functionality.
- The independent control layer.
- Project context management.
- Stage handoff mechanisms.
- Stage-level conversation workflows.

These results validate the tested implementation behavior but do not guarantee the security of the actual execution environment.

### Run the Tests

From PowerShell:

```powershell
python -m pytest -o addopts='' -q --basetemp=F:/cffmam/.pytest_cache/fresh-gate-check
```

Choose a fresh temporary directory when repeating the test run.

### Technical References

- [Architecture, Trust Boundaries, and Commands](docs/GATE.md)
- [Example Behavioral Acceptance Criteria](examples/expense_cli/acceptance.json)
- [Core Control Engine](src/csef_gate/core.py)
- [Codex Integration and Execution Restrictions](src/csef_gate/backends.py)
- [Control Layer Tests](tests/gate/test_gate.py)
- [Code Generated by the Real Coding Agent](examples/expense_cli/generated/expenses.py)

---

## 6. Legacy Components and Compatibility

Previous models, reports, and implementation artifacts are retained in:

- `src/csef_contracts`
- `compatibility`
- `verification_step5`

The previous project documentation is also preserved:

[Archived Legacy README](docs/LEGACY-README.md)

These components remain available for historical reference and compatibility purposes.

**They are not authorized to issue approvals for the new evaluation workflow.**

The earlier D1 engineering decision concerning virtual-machine isolation remains unimplemented.

---

## 7. Current Project Status

| Component | Status |
|---|---|
| Independent evaluation architecture | Implemented in local pilot |
| Separate control repository | Implemented |
| Structured JSON change proposals | Implemented |
| Black-box application execution | Implemented |
| Behavioral acceptance validation | Implemented |
| Failure detection and correction loop | Demonstrated |
| Persistent execution limits | Implemented |
| Stage-based context management | Implemented |
| Repository test suite | 133 tests passed |
| Local TCP isolation | Incomplete |
| Production-grade isolation | Not established |
| Virtual-machine isolation (D1) | Not implemented |
| Production deployment readiness | Not established |

### Conclusion

CSEF demonstrates a practical approach to independently evaluating an existing AI coding agent without relying on the agent's own claims of correctness.

The local pilot successfully demonstrated the complete correction and re-evaluation cycle, improving behavioral acceptance results from 9 passing criteria to 14 out of 14.

The central architectural principle is:

**The coding agent proposes. The independent evaluator verifies. The control layer determines whether acceptance is authorized.**

The next engineering priority is to address the remaining host-isolation limitations before considering the system suitable for security-sensitive or production use.
CSEF اکنون یک لایهٔ کنترل و ارزیابی است: Codex نصب‌شده پیشنهاد تغییر می‌دهد؛ ارزیاب جدا، برنامه را به‌صورت جعبه‌سیاه اجرا می‌کند و خروجی واقعی را با معیارهای از پیش تعیین‌شده می‌سنجد. ادعای عامل مجوز پذیرش نیست.

این نسخه یک پایلوت محلی برای CLI پایتون با کتابخانهٔ استاندارد است. هدف آن اثبات مسیر واقعی شکست، اصلاح توسط عامل موجود و ارزیابی دوباره است.

## مسیر مرحله‌ای و پروندهٔ هدف

شناخت مسئله → معماری → قراردادها → اولین مسیر کامل → توسعه → تحویل.
تعداد و نقش مراحل قابل تنظیم است. هر نقش پروندهٔ نسخه‌دار هدف و تصمیم‌ها و تحویل
بررسی‌شدهٔ قبلی را می‌گیرد؛ پیشنهاد مدل، هدف پذیرفته‌شده را بی‌صدا تغییر نمی‌دهد.
دستیار مرحله می‌تواند سؤال ضروری بپرسد و تا پاسخ کاربر، فراخوانی تکراری انجام نمی‌شود.

در مقایسهٔ کوچک انجام‌شده، هر سه روش تاریخچهٔ کامل، پروندهٔ فشرده، و پرونده با بازبین
همیشگی، ۲۵ بررسی رفتاری مرحله‌ای را گذراندند. با سهم یکسان مراحل طراحی، پروندهٔ فشرده
۸٫۶۸٪ ورودی کمتر مصرف کرد؛ بازبین همیشگی ۵۲٫۸۵٪ ورودی بیشتر از پروندهٔ تنها مصرف کرد.
این اعداد قیمت دلاری یا تضمین کیفیت پروژهٔ پیشرفته نیستند.

مسیر ادامه: پروندهٔ پایدار، کنترل ماشینی پیوسته، و بازبین مدل در تصمیم‌های معماری و
نقاط پرریسک؛ حالت بازبینی همهٔ مراحل هم موجود است. برتری کیفیت سیاست هدفمند هنوز
در پروژه‌های متنوع سنجیده نشده است.

- [روش عملیاتی و سؤال‌های مرحله‌ای](docs/WORKFLOW.md)
- [نقشهٔ کامل ادامه، کدها، اتصال‌ها و backlog](docs/MASTER-PLAN.fa.md)
- [گزارش مقایسه](docs/evidence/handoff-screening-2026-11-15/summary.json)
- [تصمیم مهندسی بر مبنای نتایج](docs/decisions/DEC-003-staged-context-and-review.md)
- [نمونهٔ ماژولار ساخته‌شده](examples/handoff_expenses/README.md)

## اجرا

برای **ساخت خود CSEF با Codex**: [راهنمای شروع و نصب افزونهٔ محلی](docs/START-CODEX.fa.md)،
[دستور آمادهٔ شروع](docs/progress/START-PROMPT.txt) و [راهنمای عامل](AGENTS.md).
این بسته وضعیت کارها را جدا از نقشهٔ پیشنهادی ثبت می‌کند و مجوز انتشار صادر نمی‌کند.

از ریشهٔ پروژه در PowerShell:

```powershell
python csef.py init --control 'C:/Users/Kp/Documents/ChatGPT/cffmam/csef-control/my-pilot' --project 'F:/cffmam/examples/expense_cli/project' --spec 'F:/cffmam/examples/expense_cli/acceptance.json'
python csef.py run --control 'C:/Users/Kp/Documents/ChatGPT/cffmam/csef-control/my-pilot'
```

پوشهٔ کنترل باید تازه و خارج از پوشهٔ پروژه باشد. پایتون و Codex باید نصب باشند و ورود Codex فعال باشد. از حساب موجود استفاده می‌شود؛ کلید تازه‌ای لازم نیست.

## محدودیت واقعی میزبان

منع خواندن/نوشتن مخزن کنترل و منع تغییر فایل‌های اجرایی در بررسی عملی موفق شد، اما اتصال TCP محلی همچنان ممکن است. مسیر عادی این وضعیت را BLOCKED می‌کند و checkpoint نمی‌سازد.

برای نمونهٔ محلی بازبینی‌شده، حالت سنجش وجود دارد:

```powershell
python csef.py run --control 'C:/Users/Kp/Documents/ChatGPT/cffmam/csef-control/my-pilot' --measure-only
```

این حالت شکست را می‌بیند، از Codex اصلاح می‌گیرد و دوباره می‌سنجد. حتی با موفقیت تمام معیارها، نتیجه review و خروج ۲ است و هرگز checkpoint صادر نمی‌کند. این حالت برای کد خصمانه، پروژهٔ حساس یا استقرار واقعی نیست.

## آنچه پیاده شده

- مشخصات، آزمون‌های پذیرش و نسخهٔ اولیه در مخزن کنترل جدا ثبت می‌شوند.
- عامل فقط پیشنهاد JSON برای مسیرهای صریحاً مجاز می‌دهد.
- ارزیاب هیچ کد یا آزمونی از برنامه را در فرایند خودش وارد نمی‌کند.
- اجرای برنامه در فرایند جدا با محدودیت سیستم‌عامل Codex انجام می‌شود.
- خروج واقعی، JSON، تمام معیارها و نسخهٔ دقیق فایل‌ها بررسی می‌شوند.
- تأیید فقط از نتیجهٔ کامل ثبت‌شده در مخزن کنترل صادر می‌شود؛ مجوزهای مدل‌های قدیمی اختیار تأیید ندارند.
- سقف تلاش و زمان پایدار است؛ مصرف گزارش‌شده ثبت می‌شود، اما قیمت و سقف دلاری ادعا نمی‌شود.

## آزمون و راهنما

نتیجهٔ اجرای واقعی ۲۰۲۶-۱۱-۱۵: در یک اجرای تازه و بدون تغییر دستی در چرخه، Codex با یک پیشنهاد، نمونه را از ۹ معیار موفق به ۱۴ از ۱۴ رساند. نتیجه REVIEW باقی ماند و درخواست checkpoint رد شد. [گزارش اجرای کامل](docs/evidence/gate-pilot-2026-11-15/clean-summary.json).

۱۳۳ آزمون مخزن موفق شدند، شامل آزمون‌های قبلی، لایهٔ کنترل و پرونده/تحویل/گفتگوی مرحله‌ای. این عدد، تضمین امنیت محیط اجرای واقعی نیست.

```powershell
python -m pytest -o addopts='' -q --basetemp=F:/cffmam/.pytest_cache/fresh-gate-check
```

برای اجرای مجدد، مسیر موقت تازه‌ای انتخاب کنید.

- [معماری، مرز اعتماد و فرمان‌ها](docs/GATE.md)
- [معیارهای رفتاری نمونه](examples/expense_cli/acceptance.json)
- [هستهٔ کنترل](src/csef_gate/core.py)
- [اتصال به Codex و محدودیت اجرا](src/csef_gate/backends.py)
- [آزمون‌های کنترل](tests/gate/test_gate.py)
- [کد تولیدشده توسط عامل واقعی](examples/expense_cli/generated/expenses.py)

## سابقه

مدل‌ها و گزارش‌های قبلی در src/csef_contracts، compatibility و verification_step5 حفظ شده‌اند؛ [README قبلی](docs/LEGACY-README.md) نیز بایگانی شده است. این بخش‌ها مرجع صدور تأیید مسیر جدید نیستند. تصمیم قدیمی D1 دربارهٔ VM همچنان پیاده نشده است.
