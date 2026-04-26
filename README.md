# ResearchWiki

> 연구를 진행하는 동안 **살아있는 연구 저널** — 구조화되고, 교차 링크되어 있고, 정직한 — 을 함께 유지해주는 LLM 코딩 에이전트용 스킬 셋.

[Codified Context](https://arxiv.org/abs/2602.20478) 프레임워크를 연구 도메인에 수직 적용한 결과물.

## 상태

**Draft v0.3 — 5개 MVP + 2개 retrieval + 1개 remediation 스킬, 모든 spec과 구현이 완료됨.**

이 저장소는 8개 스킬 전부에 대한 아키텍처 명세, 스킬별 설계 문서(`SPEC.md`), `SKILL.md` 문서, Python 구현을 포함합니다: 5개 MVP 스킬(`wiki-init`, `wiki-log`, `wiki-sync`, `wiki-deepscan`, `wiki-lint`), 2개 retrieval 확장(`wiki-query`, `wiki-recall`), 그리고 body / frontmatter 디커플링 갭을 엄격한 P3 준수 하에 닫는 1개 remediation 스킬(`wiki-fix-stale`). `wiki-log` 만 Python + LLM 하이브리드 (대화형 인터뷰와 P8 감지가 LLM 추론을 요구하기 때문) 이고, 나머지 7개는 순수 코드입니다. 다른 언어 `wiki-sync` 스캐너와 release packaging은 아직 미구현 — 아래 "아직 안 된 것" 참조.

## 어떤 문제를 해결하나

연구자는 동시에 세 형태의 지식을 쌓아갑니다: 작성하는 코드, 읽는 논문, 돌리는 실험. 그 사이의 연결 — 어느 코드가 어느 논문의 아이디어를 구현했는지, 어느 실험이 어느 가설을 검증했는지, 어느 디자인 결정이 어느 모순을 해소했는지 — 에 진짜 이해가 산다. 이 연결은 잘 기록되지 않습니다. 연구자의 머릿속에 있다가 잊혀지고, 다시 발견해야 합니다.

기존 도구는 이 셋 중 하나만 다룹니다. Zotero는 논문, MLflow는 실험, Understand-Anything은 코드. 그 어느 것도 *교차점* 을 다루지 않습니다.

ResearchWiki는 그 접합 레이어입니다. 이 스킬 셋을 가진 LLM 에이전트가 셋 모두를 가로질러 링크하는 마크다운 위키를 유지하고, 연구가 진화함에 따라 갱신하며, **추측하기를 거부합니다.**

## 작동 방식

`wiki/` 디렉토리 내에 협력하는 세 레이어:

- **Wiki Layer** — 연구자의 해석, 결정, 논문 요약 (매일 업데이트, 사람이 작성하고 LLM이 보조)
- **Index Layer** — 현재 코드베이스의 가벼운 사실 스냅샷 (필요 시 재생성)
- **Deep Analysis Layer** — [Understand-Anything](https://github.com/Lum1104/Understand-Anything) 통한 선택적인 풍부한 코드 지식 그래프 (주간/마일스톤 단위 재생성)

8개 스킬 — 5개 MVP, 2개 read-only retrieval 확장, 1개 remediation:

| 스킬 | 언제 쓰나 | 등급 |
|---|---|---|
| `wiki-init` | 최초 1회 셋업 | MVP |
| `wiki-log` | 새 엔트리 기록 (실험 / 논문 / 결정 / 메모) | MVP |
| `wiki-sync` | 매일 코드 인덱스 갱신 + stale 링크 체크 + 역방향 ref 인덱스 | MVP |
| `wiki-deepscan` | 주간 / 마일스톤 단위 deep 지식 그래프 갱신 | MVP |
| `wiki-lint` | 위키 헬스 감사 — 깨진 링크, speculation, 누락, 모순 | MVP |
| `wiki-query` | 위키 본문 자연어 검색 (read-only) | extension |
| `wiki-recall` | 최근 활동 대비 stale-but-relevant 페이지 surfacing (read-only) | extension |
| `wiki-fix-stale` | 미해결 stale ref를 연구자와 함께 순회하며 occurrence 별 승인된 본문 편집 적용 | remediation |

## 8개의 원칙

설계는 `ARCHITECTURE.md §1.4` 에 정의되고 `CLAUDE.md` 에서 강제되는 8개의 번호 매겨진 원칙으로 통제됩니다. 가장 중요한 것:

- **P1 — 사실(fact)과 해석(interpretation)을 분리.**
- **P3 — 스킬은 제안만 한다. 해석을 묵묵히 변경하지 않는다.**
- **P7 — 모든 주장은 provenance 를 가진다.**
- **P8 — 분석은 OK, 추측은 금지.**

P8이 설계의 심장입니다. LLM 에이전트는 원천에 근거할 수 있는 것만 씁니다. 근거할 수 없으면 명시적으로 그렇다고 말합니다. 추측은 (만약 발생한다면) `[speculation]` 으로 태그하고 격리합니다.

## 저장소 구조

```
.
├── README.md                       ← 지금 여기
├── ARCHITECTURE.md                 ← 전체 설계 근거 (두 번째로 읽기)
├── CLAUDE.md                       ← ResearchWiki 저장소에 작용하는 LLM 에이전트의 헌법
├── skills/                         ← 스킬별 SPEC.md (설계) + SKILL.md (구현)
│   ├── wiki-init/                  ← MVP — SPEC.md + SKILL.md + reference/ (init-time 복사용 헌법 + 설정 + 템플릿 번들)
│   ├── wiki-log/                   ← MVP — SPEC.md + SKILL.md
│   ├── wiki-sync/                  ← MVP — SPEC.md + SKILL.md
│   ├── wiki-deepscan/              ← MVP — SPEC.md + SKILL.md
│   ├── wiki-lint/                  ← MVP — SPEC.md + SKILL.md
│   ├── wiki-query/                 ← extension (retrieval) — SPEC.md + SKILL.md
│   ├── wiki-recall/                ← extension (surfacing) — SPEC.md + SKILL.md
│   └── wiki-fix-stale/             ← remediation — SPEC.md + SKILL.md
├── prompts/                        ← 작성 가이드
│   ├── writing-skill-md.md         ← 이 프로젝트용 SKILL.md 작성법
│   ├── enforcing-p8.md             ← 가장 어려운 원칙의 운영 디테일
│   └── skill-interplay-scenarios.md← 스킬 조합의 6개 워크 스루
└── docs/                           ← 장문 문서 자리 (TBD)
```

신규 컨트리뷰터의 읽는 순서:

1. 이 README
2. `ARCHITECTURE.md`
3. `CLAUDE.md`
4. 감을 잡기 위해 한 스킬의 SPEC.md (`wiki-log` 부터)
5. `prompts/enforcing-p8.md`

## Claude Code 플러그인으로 설치

이 저장소는 [Claude Code 플러그인](https://code.claude.com/docs/en/plugins.md) 입니다 — 루트에 `.claude-plugin/plugin.json` 매니페스트, `skills/` 아래에 8개 스킬. 설치 후 모든 스킬은 플러그인 이름으로 namespace 된 슬래시 커맨드가 됩니다 (예: `/researchwiki:wiki-log`).

**전제 조건 — Python 패키지.** 스킬의 `SKILL.md` 가 호출하는 CLI 커맨드(`wiki-init`, `wiki-log`, `wiki-sync`, ...)는 이 저장소의 Python 패키지가 제공합니다. 먼저 설치:

```bash
git clone https://github.com/apple4ree/researchwiki.git
cd researchwiki
pip install -e .
```

(7개의 Class A 스킬은 순수 Python; `wiki-log` 만 Python + LLM 하이브리드 — `ARCHITECTURE.md §3.5` 참조.)

**플러그인 설치.** 두 갈래:

- **로컬 개발** — Claude Code를 클론한 저장소로 가리킴:
  ```bash
  claude --plugin-dir /path/to/researchwiki
  ```
  Claude Code 안에서: `/researchwiki:wiki-init`, `/researchwiki:wiki-log`, ...

- **Marketplace 경유** — `.claude-plugin/marketplace.json` 저장소에 publish 된 후:
  ```
  /plugin marketplace add <org>/<plugin-repo>
  /plugin install researchwiki@<marketplace-name>
  ```

**Bundle 경로 해석.** `wiki-init` 은 init 시점에 대상 저장소로 그대로 복사되는 런타임 자산 번들(`skills/wiki-init/reference/bundle/`)을 함께 배포합니다. locator(`src/researchwiki/init.py:_find_bundle`)는 환경 변수 오버라이드(`RESEARCHWIKI_BUNDLE`, `CLAUDE_PLUGIN_ROOT`) 를 먼저 시도하고, 없으면 source-relative 경로로 fallback. editable install (`pip install -e .`) 과 Claude Code 매니지드 플러그인 설치 둘 다 추가 설정 없이 동작.

## 구현된 것

소스는 `src/researchwiki/` 아래. CLI 진입점은 `pip install -e .` 로 노출.

- **`wiki-init` v0.1** — 번들(`skills/wiki-init/reference/bundle/{CLAUDE.md, research-wiki.config.yaml, templates/<lang>/}`)을 대상 저장소로 복사하고 wiki/index/deep/raw/templates 디렉토리 골격을 만들어 ResearchWiki 워크스페이스로 부트스트랩. `--language` 에 따라 `language.default` 만 후처리 치환 (그 외엔 byte-for-byte 그대로). 4개 wiki 메타 파일(index/log/questions/discrepancies) 생성, init 이벤트를 첫 log entry 로 append. Idempotent — 재실행 시 기존 파일 skip 후 새 init 로그만 추가. `.gitignore` 에 `deep/knowledge-graph.json` 추가 (idempotent). CLI: `wiki-init [target] --mode new --language ko -y`.
- **`wiki-sync` v0.1** — Python (stdlib `ast`), JSON (top-level keys), Markdown (ATX headings, frontmatter / code-fence aware) 스캐너. `index/signatures.json`, `index/reverse_refs.json`, 실행별 `index/snapshots/sync_*.md` 생성. Stale-link pass가 frontmatter `stale: true` 표시 + `wiki/questions.md` append (재실행 시 idempotent; 위키 본문은 절대 건드리지 않음). CLI: `wiki-sync --repo <path>`.
- **`wiki-lint` v0.1** — 8개의 mechanical check: frontmatter schema, `authored_by` enum, intra-wiki 링크 존재(Obsidian-style root-relative 해석), `refs.code.path` 파일 존재, speculation 밀도(default 0.30 임계치), 지속 stale-ref 나이(default 7일), cross-page `confidence` 충돌, `seeded_by:` grace period(default 30일) 가진 orphan 페이지. 메타 페이지는 frontmatter/speculation 검사에서 제외. 감사 리포트 + `wiki/questions.md` / `wiki/discrepancies.md` append. release gating용 `--strict`. CLI: `wiki-lint --repo <path>`.
- **`wiki-deepscan` v0.1** — 외부 지식 그래프 도구(주로 Understand-Anything)의 wrapper. 그래프를 로드(혹은 바이너리 호출)하고, inbound-edge 임계치로 architecturally significant 노드 필터링, wiki concept stub seeding (frontmatter-only + 구조적 사실 + open-questions 템플릿 — LLM이 prose 작성 절대 안 함), 같은 concept 의 기존 페이지에 verified `refs.code` append, naming 충돌(→ `wiki/questions.md`)과 graph-vs-frontmatter 불일치(→ `wiki/discrepancies.md`) 감지. `deep/knowledge-graph.json`, `deep/last-scan.yaml`, 실행별 `deep/deepscan-report-*.md` 작성. `--from-graph <path>` 로 미리 빌드된 그래프 주입 가능 (테스트 / 비-UA 도구용). CLI: `wiki-deepscan --repo <path>`.
- **`wiki-query` v0.1** — 위키 본문 BM25 lexical 검색. 토크나이저는 식별자 구분자(snake/camel/kebab + 점/슬래시)로 분할하면서도 정확 경로 검색을 위해 통째 청크도 보존; ko/en 혼용 유지. 추출형 스니펫과 함께 ranked 페이지 경로를 stdout 출력. 미해결 `stale: true` 플래그가 있는 페이지는 `⚠ stale: …` 배지 prefix 부착. 메타 페이지는 기본 제외; `--include-meta` 로 포함. `--scope`, `--top`, `--frontmatter-only`, `--no-stale-warnings` 플래그. stdlib 만 사용. CLI: `wiki-query "rotary attention" --repo <path>`.
- **`wiki-recall` v0.1** — 최근 `wiki/log.md` 활동 ref 와 stale 페이지 frontmatter 의 교집합으로 stale-but-relevant 페이지를 surfacing. 스킬-메타 entry(`from wiki-sync`, `from wiki-lint`, `from wiki-deepscan`)는 헤더 패턴으로 필터. 기본 ref 가중치: code=2.0, concepts=1.5, papers=1.0, experiments=1.0. `seeded_by:` / `authored_by: llm` 인 빈-본문 stub은 기본 제외; `--include-stubs` 로 포함. `--lookback`, `--stale-since`, `--scope`, `--top` 플래그. CLI: `wiki-recall --repo <path>`.
- **`wiki-sync` v0.2** — v0.1 위에 세 가지 추가:
  - `--scan-body` body link rot (opt-in 휴리스틱). 위키 본문을 multi-cap-PascalCase + dotted + paren-suffix 정규식으로 토큰화 (영어 false positive `Use` / `Set` 등 회피). index에 없는 토큰을 frontmatter 의 `body_stale_mentions: [{line, token, detected}]` 로 기록. 암묵적 `[unverified]`.
  - **Rename 휴리스틱.** 심볼 diff 후 same path + 라인 근접성 + `difflib` signature 유사도(default 0.80)로 removed × added 심볼 페어링. snapshot 의 `## Possible renames (heuristic, [unverified])` 섹션에 출력. `sync.rename_heuristic.{enabled, similarity_threshold, line_window}` 로 설정.
  - **End-of-run nag.** `sync.nag_after_days`(default 7) 보다 오래된 미해결 `stale: true` 플래그 존재 시 `⚠ stale 플래그 N개, X일 이상 미해결. wiki-fix-stale로 처리하시겠어요?` 출력. `--no-nag` 로 억제.
- **`wiki-fix-stale` v0.1** — 위키 본문을 합법적으로 편집하는 *유일한* P3-carve-out 스킬. 연구자-주도 호출 + occurrence 별 승인 + 4개 mechanical 변환(연구자가 제공한 식별자로 심볼 교체 / `[deprecated YYYY-MM-DD]` 태그로 감싸기 / 라인 삭제 / skip)만 수행. 페이지의 모든 occurrence가 처리되면 `stale: true` 플래그와 `body_stale_mentions:` entry 가 frontmatter에서 자동 클리어. frontmatter `refs.code` stale 플래그 AND `wiki-sync --scan-body` 의 `body_stale_mentions:` 둘 다 순회. 세션 기록을 `wiki/log.md` 에 append. 페이지 단위 atomic (페이지 중간 abort 시 in-memory 편집 폐기). 테스트 가능성을 위한 의존성 주입 `prompt_fn` / `display_fn`. CLI: `wiki-fix-stale --repo <path>`.
- **`wiki-log` v0.1 (Python + LLM 하이브리드)** — *유일한* LLM-필수 스킬. Mechanical core(`src/researchwiki/log.py` + 5개 CLI 서브커맨드: `inspect`, `lookup-symbols`, `find-pages`, `find-amend-target`, `run`)가 템플릿 파싱(HTML 주석 처리, `{{PLACEHOLDER}}` 인용), `index/signatures.json` 조회, exact-slug 페이지 조회, entry + log.md append + index.md 갱신 + 양방향 back-ref + concept stub 생성 + questions.md append 의 atomic write를 담당. 대화형 인터뷰(이탤릭 가이드 paraphrase, P8 감지 + 3-route 흐름, identifier / 명사구 추출, 요약 작성)는 LLM의 몫이며 `skills/wiki-log/reference/` 의 9개 reference 문서 (`p8-detection.md`, `conversational-style.md`, `auto-link-extraction.md`, `refusal-patterns.md`, `templates-deep-dive.md` 등) 가 가이드. `authored_by: llm` 은 validator 가 거부 — 모든 entry 는 사람의 의도를 요구. CLI: `wiki-log {inspect | lookup-symbols | find-pages | find-amend-target | run} ...`.
- **`docs/CONFIG.md`** 와 **`docs/TEMPLATES.md`** — 사용자용 reference 문서. 스킬별 `consumed-config.md` 와 wiki-log 템플릿 포맷을 모은 통합본.
- **Integration 테스트** — `tests/integration/` 아래. `wiki-init` 으로 부트스트랩한 임시 디렉토리 fixture 위에서 cross-skill 데이터 흐름 검증. 5개의 end-to-end 시나리오(refactor remediation, weekly audit + query + recall, deepscan stub × lint orphan grace, body link rot round trip, wiki-log 전체 CLI 흐름) + 2개의 pairwise 계약(recall이 스킬-메타 로그 entry 를 필터, fix-stale이 lint 가 보고하는 같은 finding 을 클리어).

168 테스트 전부 통과 (159 unit + 9 integration).

## 아직 안 된 것

- `wiki-sync` 의 다른 언어 스캐너 (TypeScript / JavaScript via tree-sitter, ctags fallback)
- Release packaging (license, classifiers, CI, PyPI)

## 라이선스 / 상태

이 프로젝트는 궁극적인 오픈소스 공개를 염두에 두고 설계되었습니다. 라이선스 선정 및 공개 시점은 저자의 판단에 따릅니다.

파생 작업에는 Codified Context (arXiv:2602.20478)와 Understand-Anything (github.com/Lum1104/Understand-Anything) 인용이 필수입니다.
