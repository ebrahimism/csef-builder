# کدها و ماژول‌های لازم برای ادامهٔ CSEF

وضعیت همهٔ مسیرهای هدف: **پیشنهادی و هنوز ساخته‌نشده**، مگر در جدول کدهای موجود. این جدول نقشهٔ مسئولیت است؛ جداسازی به فایل مستقل وقتی انجام می‌شود که پیچیدگی و آزمون آن را توجیه کند. پوشه‌های `lifecycle` و `reviewing` عمداً با `project.py` و `review.py` فعلی هم‌نام نیستند تا importهای موجود شکسته نشوند.

## کدهای فعلی: نگه‌داری، نه بازنویسی کامل

| کد | تصمیم |
| --- | --- |
| `project.py` | حفظ public API ProjectBook؛ انتقال تدریجی storage/lifecycle/context |
| `assistant.py` | حفظ assist_stage؛ استخراج interview و application service |
| `review.py` | حفظ route_review و review_proposal؛ استخراج policy و semantic review |
| `model_session.py` | یکی‌شدن با مسیر مشابه در backends.py پشت ModelProvider |
| `backends.py` | حفظ facadeهای اجرا؛ انتقال transportها به providers/execution |
| `core.py` | حفظ Gate؛ استخراج proposal/verification/authority با آزمون‌های منفی |
| `project_cli.py / __main__.py` | delegation به interfaces/cli و application service |
| `src/csef_contracts/` | نگهداری به‌عنوان سابقه؛ بدون اختیار صدور تأیید و بدون ادغام کور |

## قرارداد مشترک هر ماژول

ورودی/خروجی نسخه‌دار؛ عدم دسترسی مستقیم مدل به مرجع اختیار؛ خطای نوع‌دار؛ ثبت intent برای اثر خارجی؛ state قابل ادامه؛ هیچ side effect هنگام import. APIهای زیر امضای هدف‌اند و پیاده‌سازی فعلی محسوب نمی‌شوند.

## contracts

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M001 | `src/csef_gate/contracts.py` | ProjectRevision، StageSpec، Proposal، ModelReceipt، VerificationReceipt و خطاهای نوع‌دار | `ProjectRevision; StageSpec; ModelRequest/Result; ChangeProposal; ExecutionReceipt; VerificationRecord` | T003 |

## persistence

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M002 | `src/csef_gate/persistence/sqlite.py` | تراکنش‌ها و repository واحد کنترل | `transaction(); project_repository(); run_repository(); promote_transaction()` | T003 |
| M003 | `src/csef_gate/persistence/migrations.py` | مهاجرت نسخه‌دار و backup پیش از تغییر | `preflight(); migrate(from_version, to_version); rollback_copy()` | T003 |
| M004 | `src/csef_gate/persistence/artifacts.py` | ذخیرهٔ محتوایی فایل با digest و محدودیت اندازه | `put(bytes); get(hash); verify(manifest); export_allowed()` | T004 |
| M005 | `src/csef_gate/persistence/events.py` | ثبت intent/outcome و رویدادهای پایدار | `append_intent(); append_outcome(); replay(project_id)` | T004 |
| M006 | `src/csef_gate/persistence/leases.py` | قفل پروژه/مرحله و جلوگیری از اجرای متناقض | `acquire(project_id); heartbeat(); release()` | T004 |

## lifecycle

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M007 | `src/csef_gate/lifecycle/projects.py` | ساخت و خواندن پرونده، نسخه و scope | `create(); current_revision(); status(); assert_revision()` | T005 |
| M008 | `src/csef_gate/lifecycle/requirements.py` | منشأ نیاز، اهمیت و وضعیت پذیرش | `record_statement(); propose(); accept(); supersede()` | T005 |
| M009 | `src/csef_gate/lifecycle/decisions.py` | ADR و گزینه‌های ردشده با دلیل | `propose_adr(); adopt_decision(); affected_requirements()` | T005 |
| M010 | `src/csef_gate/lifecycle/questions.py` | پرسش‌های باز، پاسخ و اصلاح پاسخ | `ask_if_material(); answer(); revise_answer(); unresolved()` | T006 |
| M011 | `src/csef_gate/lifecycle/change_control.py` | پیشنهاد تغییر و invalidation وابستگی‌ها | `propose_change(); authorize_change(); impact(); invalidate_descendants()` | T008 |

## workflow

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M012 | `src/csef_gate/workflow/engine.py` | هماهنگی نقش، پیشنهاد، ارزیابی و تحویل | `run_stage(); dispatch_role(); validate_outputs(); complete_handoff()` | T007 |
| M013 | `src/csef_gate/workflow/stages.py` | ثبت مرحله، پیش‌شرط و نمودار وابستگی | `register(); eligible_stages(); assert_dependencies()` | T007 |
| M014 | `src/csef_gate/workflow/handoffs.py` | بستهٔ تحویل با source/spec/policy hashes | `build_packet(); verify_bytes(); consume_current()` | T007 |
| M015 | `src/csef_gate/workflow/recovery.py` | resume و reconciliation نتیجهٔ نامعلوم | `reconcile_intent(); resume(); classify_unknown()` | T008 |

## context

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M016 | `src/csef_gate/context/index.py` | ایندکس فایل/هش/نماد و FTS5 | `index_snapshot(); ast_symbols(); changed_files()` | T009 |
| M017 | `src/csef_gate/context/retrieval.py` | بازیابی فایل‌ها و اسناد مرتبط با کار جاری | `search_text(); related_files(); mandatory_facts()` | T009 |
| M018 | `src/csef_gate/context/packets.py` | سقف زمینه، facts اجباری و حذف صریح | `compile_packet(); enforce_budget(); disclose_omissions()` | T010 |
| M019 | `src/csef_gate/context/traceability.py` | اتصال نیاز به تصمیم، کد و معیار مشاهده | `link_requirement(); uncovered_requirements(); stale_links()` | T010 |

## engineering

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M020 | `src/csef_gate/engineering/interview.py` | مصاحبهٔ نقش‌محور با سؤال ضروری | `extract_statements(); detect_conflicts(); choose_questions()` | T011 |
| M021 | `src/csef_gate/engineering/architecture.py` | گزینه‌ها، NFR و ADR پیشنهادی | `compare_options(); propose_adr(); scenario_review()` | T012 |
| M022 | `src/csef_gate/engineering/planning.py` | برش عمودی، ریسک، ترتیب و معیار ساخت | `vertical_slices(); dependency_plan(); stage_criteria()` | T012 |
| M023 | `src/csef_gate/engineering/templates.py` | قالب‌های وابسته به نوع محصول، نه وب اجباری | `select(product_kind); render(); resolve_override()` | T012 |

## providers

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M024 | `src/csef_gate/providers/base.py` | ModelProvider Protocol و request/response مشترک | `ModelProvider; ModelCapabilities; ModelRequest; ModelResult` | T013 |
| M025 | `src/csef_gate/providers/registry.py` | قابلیت، شناسه و تنظیمات فراهم‌کننده | `register(); resolve_route(); require_capabilities()` | T014 |
| M026 | `src/csef_gate/providers/codex_cli.py` | تولید schema-bound با ورود موجود Codex | `generate_schema(); parse_events(); capture_usage()` | T013 |
| M027 | `src/csef_gate/providers/openai_compatible.py` | Responses و Chat با endpoint انتخاب‌شده | `generate_responses(); generate_chat(); translate_errors()` | T015 |
| M028 | `src/csef_gate/providers/ollama.py` | درخواست به مدل محلیِ از قبل نصب‌شده | `generate_local(); list_local_models(); probe_schema()` | T017 |
| M029 | `src/csef_gate/providers/health.py` | probe، timeout و circuit breaker | `probe(); record_failure(); circuit_state(); retry_after()` | T014 |
| M030 | `src/csef_gate/providers/router.py` | انتخاب بر اساس نقش، کیفیت، هزینه و سیاست داده | `select_for_role(); permitted_fallbacks(); stop_if_unpriced()` | T016 |
| M031 | `src/csef_gate/providers/usage.py` | usage واقعی، cached/uncached و نتیجهٔ نامعلوم | `record_reported_usage(); mark_unknown(); aggregate()` | T016 |
| M032 | `src/csef_gate/providers/pricing.py` | قیمت نسخه‌دار و رزرو/تسویهٔ هزینه | `price_snapshot(); reserve_upper_bound(); settle_once()` | T016 |
| M033 | `src/csef_gate/providers/secrets.py` | ارجاع به اعتبارنامه بدون قراردادن در prompt/guest | `resolve_reference(); scoped_environment(); redact()` | T015 |

## coding

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M034 | `src/csef_gate/coding/base.py` | CodingAgent Protocol مستقل از LLM transport | `CodingAgent; TaskPacket; SourceSnapshot; ChangeProposal` | T018 |
| M035 | `src/csef_gate/coding/codex.py` | ترجمهٔ کار محدود به درخواست عامل موجود | `propose_scoped_change(); parse_proposal(); cancel_attempt()` | T018 |
| M036 | `src/csef_gate/coding/proposals.py` | proposal با base revision و عملیات فایل مشخص | `validate_envelope(); bind_base_revision(); diff_summary()` | T018 |
| M037 | `src/csef_gate/coding/scope.py` | allowlist، traversal، reparse و تست‌های محافظت‌شده | `validate_path(); assert_allowed_changes(); protect_oracle()` | T018 |
| M038 | `src/csef_gate/coding/apply.py` | اعمال اتمیک/قابل‌بررسی تغییر به candidate | `stage_operations(); apply_to_candidate(); verify_result_tree()` | T018 |
| M039 | `src/csef_gate/coding/impact.py` | اثر تغییر بر قرارداد و آزمون و اسناد | `changed_contracts(); affected_tests(); affected_documents()` | T020 |
| M040 | `src/csef_gate/coding/aider.py` | آداپتر جایگزین مشروط به spike؛ مشروط | `probe_cli(); propose_in_workspace(); export_candidate_diff()` | T020 |

## workspace

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M041 | `src/csef_gate/workspace/git.py` | وضعیت Git، worktree، diff و بازگشت محدود | `inspect_status(); create_owned_worktree(); diff(); rollback_owned()` | T019 |
| M042 | `src/csef_gate/workspace/github.py` | خواندن remote و PR در scope صریح | `read_repository(); read_issue(); read_ci(); create_scoped_draft_pr()` | T031 |
| M043 | `src/csef_gate/workspace/snapshots.py` | manifest کامل نسخهٔ تست‌شده | `snapshot_source(); fingerprint_tree(); assert_no_unexpected_files()` | T019 |

## execution

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M044 | `src/csef_gate/execution/base.py` | ExecutionProvider و ExecutionReceipt | `provision(); execute(); collect(); cancel(); destroy()` | T021 |
| M045 | `src/csef_gate/execution/native.py` | حفظ مسیر فعلی فقط با capability مشاهده‌شده | `probe_observed_capabilities(); execute_reviewed_local_only()` | T021 |
| M046 | `src/csef_gate/execution/hyperv.py` | ایجاد/یافتن/reset مهمان اختصاصی با تنظیم صریح | `inspect_host(); create_or_attach_guest(); reset_guest(); destroy_owned_guest()` | T022 |
| M047 | `src/csef_gate/execution/ssh_guest.py` | کانال مدیریتی محدود و outcome شناخته/نامعلوم | `execute_allowlisted_request(); capture_outcome(); reconcile_disconnect()` | T022 |
| M048 | `src/csef_gate/execution/transfer.py` | انتقال manifest و خروجی allowlist | `pack_allowed_inputs(); validate_archive(); unpack_inside_root(); collect_allowed_outputs()` | T023 |
| M049 | `src/csef_gate/execution/profiles.py` | شبکه/فایل/منبع و تفکیک guest/host | `resolve_profile(); validate_network_scope(); validate_resource_limits()` | T021 |
| M050 | `src/csef_gate/execution/probes.py` | positive/negative controls مرز اجرا | `positive_controls(); deny_host_files(); deny_host_network(); deny_baseline_writes()` | T024 |

## verification

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M051 | `src/csef_gate/verification/plan.py` | تبدیل معیارها به کارهای ارزیاب مورد اعتماد | `compile_criteria(); validate_nonempty(); required_check_ids()` | T025 |
| M052 | `src/csef_gate/verification/runner.py` | اجرای ابزار و جمع‌آوری خروجی واقعی | `execute_checks(); capture_reports(); bounded_output()` | T025 |
| M053 | `src/csef_gate/verification/python_pack.py` | pytest، Ruff و mypy با parser مشخص | `pytest_plan(); parse_junit(); ruff_plan(); mypy_plan()` | T025 |
| M054 | `src/csef_gate/verification/web_pack.py` | ساخت وب و Playwright در guest | `build_plan(); browser_plan(); parse_playwright_report()` | T033 |
| M055 | `src/csef_gate/verification/architecture.py` | قواعد وابستگی و بررسی API/schema | `import_rules(); contract_compatibility(); data_owner_rules()` | T026 |
| M056 | `src/csef_gate/verification/verdict.py` | PASS/FAIL/REVIEW/STALE/UNKNOWN با شواهد کامل | `evaluate_complete_evidence(); stale_reasons(); require_review()` | T027 |
| M057 | `src/csef_gate/verification/authority.py` | ارتقای اتمیک از رکورد معتبر، نه PASS ورودی | `verify_and_record(); promote_from_store(); consume_approval_once()` | T027 |
| M075 | `src/csef_gate/verification/security.py` | اجرای بررسی اسرار و وابستگی شناخته‌شده بدون ادعای ممیزی کامل امنیت | `scan_secret_diff(); audit_locked_dependencies(); normalize_findings()` | T026 |

## reviewing

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M058 | `src/csef_gate/reviewing/policy.py` | انتخاب نقطهٔ بازبینی با سیاست صریح | `route_review(); required_signals(); policy_version()` | T028 |
| M059 | `src/csef_gate/reviewing/semantic.py` | درخواست مستقل بازبین و ارجاع به facts | `review_against_facts(); compare_proposal(); owner_questions()` | T028 |
| M060 | `src/csef_gate/reviewing/findings.py` | شدت، شاهد، پیشنهاد اصلاح و dissent | `normalize_findings(); bind_evidence(); classify_dissent()` | T028 |

## interfaces

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M061 | `src/csef_gate/interfaces/cli.py` | فرمان‌ها و سازگاری csef.py فعلی | `project_commands(); run_commands(); export_packet()` | T007 |
| M062 | `src/csef_gate/interfaces/mcp.py` | ابزارهای کنترل‌شده برای همین محیط چت | `project_create(); project_message(); question_answer(); stage_run(); verification_get()` | T029 |
| M063 | `src/csef_gate/interfaces/api.py` | API مشترک اختیاری برای UI محلی؛ مشروط | `project_endpoints(); run_events(); local_auth(); artifact_download()` | T030 |

## integrations

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M064 | `src/csef_gate/integrations/spec_kit.py` | import/export و bridge محدود Spec Kit | `import_spec(); export_approved_packet(); map_workflow_step(); verify_roundtrip()` | T002 |
| M065 | `src/csef_gate/integrations/litellm.py` | مسیر اختیاری gateway بدون تغییر core؛ بعداً | `generate_via_gateway(); normalize_usage(); enforce_route_policy()` | T037 |
| M066 | `src/csef_gate/integrations/openhands.py` | مسیر اختیاری SDK پشت CodingAgent؛ بعداً | `propose_via_sdk(); constrain_workspace(); normalize_events()` | T038 |

## delivery

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M067 | `src/csef_gate/delivery/bundle.py` | بستهٔ خروجی با manifest، lock و راهنما | `build_manifest(); package_source(); generate_runbook(); clean_install_smoke()` | T032 |
| M068 | `src/csef_gate/delivery/backup.py` | backup سازگار SQLite و artifact | `backup_sqlite(); backup_referenced_artifacts(); verify_backup()` | T032 |
| M069 | `src/csef_gate/delivery/restore.py` | restore و آزمون قابلیت استفادهٔ نسخهٔ تحویلی | `restore_to_new_location(); verify_integrity(); recovery_smoke()` | T032 |

## observability

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M070 | `src/csef_gate/observability/events.py` | پیشرفت و مصرف به زبان قابل فهم | `project_progress(); usage_summary(); explain_block()` | T034 |
| M071 | `src/csef_gate/observability/redaction.py` | حذف اسرار و سیاست نگهداری داده | `redact_secrets(); apply_retention(); export_safe_logs()` | T034 |

## evaluation

| شناسه | مسیر هدف | مسئولیت | API یا کد مورد نیاز | کار |
| --- | --- | --- | --- | --- |
| M072 | `src/csef_gate/evaluation/corpus.py` | سناریو و oracle نهایی جدا از توسعه | `load_frozen_cases(); split_development_holdout(); version_oracle()` | T035 |
| M073 | `src/csef_gate/evaluation/runner.py` | اجرای جفتی روش‌ها با بودجهٔ یکسان | `paired_runs(); fixed_budget(); randomize_order(); record_interventions()` | T035 |
| M074 | `src/csef_gate/evaluation/metrics.py` | کیفیت، مصرف، هزینهٔ معلوم و دخالت کاربر | `quality_outcomes(); known_cost(); unknown_cost(); owner_active_minutes()` | T035 |

## فایل‌های غیرماژولی

- **T001**: `docs/evidence/baseline-vnext/manifest.json`
- **T002**: `integrations/spec-kit/preset/README.md`، `integrations/spec-kit/workflows/csef-review.yml`
- **T003**: `schemas/project-v1.json`، `schemas/stage-v1.json`، `schemas/proposal-v1.json`، `schemas/verification-v1.json`
- **T011**: `templates/brief.md`، `templates/questions.md`
- **T012**: `templates/adr.md`، `templates/contracts.md`، `templates/task.md`، `templates/handoff.md`، `templates/release.md`
- **T016**: `config/providers.example.toml`، `config/budgets.example.toml`
- **T021**: `profiles/execution/guest-default.json`
- **T022**: `scripts/vm/provision.ps1`، `scripts/vm/guest-bootstrap.sh`
- **T026**: `config/architecture-rules.example.json`
- **T029**: `examples/mcp/client-configuration.example.json`
- **T030**: `ui/index.html`، `ui/chat.js`، `ui/styles.css`
- **T032**: `docs/RUNBOOK.fa.md`، `docs/BACKUP-RESTORE.fa.md`
- **T035**: `experiments/corpus/manifest.json`، `experiments/protocol-vnext.json`
- **T036**: `uv.lock`، `.github/workflows/ci.yml`، `scripts/install.ps1`، `scripts/install.sh`، `THIRD_PARTY_NOTICES.md`

فایل `csef-review.yml` تنها بعد از تأیید syntax/API نسخهٔ قفل‌شدهٔ Spec Kit ساخته می‌شود؛ این نام، ادعای وجود workflow آماده نیست. `ui/` مشروط است. migration باید با DB فعلی روی کپی آزمایش شود. فایل lock و CI پس از انتخاب نسخه‌های آزموده تولید می‌شوند، نه از HEAD مشاهده‌شده.

## طرح آزمون هر مسئولیت

هر task در [backlog](BACKLOG.fa.md) آزمون نام‌دار و معیار رفتاری دارد. آزمون فقط بازتاب تابع نیست: نسخهٔ کهنه، خروجی جعلی، قطع فرایند، replay، دادهٔ قدیمی، scope اشتباه و اختلال provider باید پوشش داده شوند. معیار کاغذی بدون ابزار/فرمان اجراشده شاهد موفقیت نیست.

## ترتیب انتقال کد

۱. facadeهای فعلی با همان رفتار باقی بمانند. ۲. یک responsibility همراه با آزمون مستقل استخراج شود. ۳. call siteهای همان مسیر منتقل شوند. ۴. گزارش و artifact نسخه‌دار با نسخهٔ قدیمی خوانده شوند. ۵. حذف wrapper فقط پس از دورهٔ سازگاری و نبود مصرف‌کننده انجام شود. 

مسیرهای پیشنهادی، تعهد به خردکردن زودهنگام یا ساخت چندین سرویس جدا نیستند؛ همه می‌توانند در یک فرایند کنترل محلی اجرا شوند.
