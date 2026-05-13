# Orarioo

Web-based system for intelligent academic schedule management.
Final Degree Project — University of Seville.

[![Django CI](https://github.com/Mialra/Orarioo/actions/workflows/django-ci.yml/badge.svg)](https://github.com/Mialra/Orarioo/actions/workflows/django-ci.yml)
[![Lint](https://github.com/Mialra/Orarioo/actions/workflows/python-lint.yml/badge.svg)](https://github.com/Mialra/Orarioo/actions/workflows/python-lint.yml)
[![CodeQL](https://github.com/Mialra/Orarioo/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/Mialra/Orarioo/actions/workflows/codeql-analysis.yml)

---

## What is Orarioo?

Orarioo lets school teams generate, visualise, and manually edit weekly timetables automatically. The NP-hard timetabling problem is solved with **Google OR-Tools CP-SAT**, a constraint-programming solver that guarantees hard constraints are never violated while optimising soft preferences.

**Key features:**

- Automatic schedule generation with hard and soft constraints (CP-SAT)
- Manual session drag-and-drop editing with conflict detection
- TC duty hour assignment (Trabajo de Centro) generated alongside the timetable
- Per-algorithm-run configuration: enable/disable each soft constraint individually
- Export to PDF and Excel
- Multi-tenant: each collaboration team has isolated data
- Full audit trail (who changed what, and when)
- GDPR compliance: personal data download, right to erasure
- Responsive design

---

## Tech Stack

| Layer             | Technology                    | Version                |
| ----------------- | ----------------------------- | ---------------------- |
| Backend framework | Django                        | 6.0.4                  |
| REST API          | Django REST Framework         | 3.15.2                 |
| Authentication    | djangorestframework-simplejwt | 5.5.1                  |
| Constraint solver | OR-Tools CP-SAT               | 9.15.6755              |
| Database          | PostgreSQL                    | psycopg2-binary 2.9.11 |
| Data analysis     | Pandas / NumPy                | 3.0.1 / 2.4.2          |
| PDF export        | ReportLab                     | 4.4.10                 |
| Excel export      | openpyxl                      | 3.1.5                  |
| WSGI server       | Gunicorn                      | 25.1.0                 |
| Static files      | WhiteNoise                    | 6.9.0                  |
| Frontend          | HTML5 + CSS + Vanilla JS      | —                      |
| Linting           | Flake8 / Black / isort        | —                      |
| Testing           | Coverage.py                   | 7.13.4                 |
| CI/CD             | GitHub Actions                | —                      |
| Security scanning | CodeQL, Bandit                | —                      |
| Hosting           | Render                        | —                      |

---

## Schedule Generation Algorithm

The generation pipeline runs entirely server-side:

```
POST /api/schedules/generate/
  |
  v
BasicScheduleGenerator
  |- Builds session list from selected subjects
  +- Builds available classroom pool
  |
  v
build_weekly_slots()          -- time windows per educational stage
  |
  v
solve_session_assignment()
  |- Phase 1 — CP-SAT feasibility (no timeout, finds any valid assignment)
  |- _add_solution_hints()    -- warm-starts Phase 2 from Phase 1 solution
  +- Phase 2 — CP-SAT optimisation (configurable timeout, default unlimited)
       Hard constraints: no double-booking, capacity limits, unavailability blocks
       Soft constraints: time preferences, day spread, teacher gap penalty
  |
  v
assign_tc_sessions()          -- greedy duty-hour assignment (if teachers_on_duty > 0)
  |
  v
ScheduleEvaluator             -- detects non-critical defects
  |
  v
Schedule + TCSession objects saved to DB
```

> **Why no post-processing?** Empirical testing showed that a greedy hill-climbing local search after Phase 2 always produced `local_search_delta = 0`: student groups are fully packed, so there is no legal slot to move a session into when filling a teacher gap. Teacher gaps are structural in this domain, not solver artefacts.

**Hard constraints** (infeasible if violated):

- Max weekly slots per group: 25h (Preschool/Primary) | 30h (Secondary)
- Max daily slots per group: 5 (Preschool/Primary) | 6 (Secondary)
- No teacher/group/classroom double-booking in the same slot
- Recess slots are never used for classes
- UNAVAILABLE teachers and subjects are excluded

**Soft constraints** (configurable per generation run):

| Objective                            | Weight | Toggle                            |
| ------------------------------------ | ------ | --------------------------------- |
| Subject in PREFER_YES slot           | +2     | `enable_subject_time_preferences` |
| Subject in PREFER_NO slot            | -2     | `enable_subject_time_preferences` |
| Teacher in PREFER_YES slot           | +2     | `enable_teacher_time_preferences` |
| Teacher in PREFER_NO slot            | -2     | `enable_teacher_time_preferences` |
| Subject spread across different days | +3/day | `enable_subject_day_spread`       |
| Teacher intra-day gap                | -8/gap | `enable_teacher_gap_minimization` |

**Generation parameters** (sent with the request):

| Parameter                          | Type | Default   | Description                                     |
| ---------------------------------- | ---- | --------- | ----------------------------------------------- |
| `enable_no_intraday_gaps`          | bool | `true`    | Forbid intra-day gaps for student groups        |
| `enable_subject_unavailable_times` | bool | `true`    | Respect subject UNAVAILABLE blocks              |
| `enable_teacher_unavailable_times` | bool | `true`    | Respect teacher UNAVAILABLE blocks              |
| `enable_subject_time_preferences`  | bool | `true`    | Apply subject PREFER_YES / PREFER_NO weights    |
| `enable_teacher_time_preferences`  | bool | `true`    | Apply teacher PREFER_YES / PREFER_NO weights    |
| `enable_subject_day_spread`        | bool | `true`    | Spread each subject across different days       |
| `enable_teacher_gap_minimization`  | bool | `true`    | Penalise teacher intra-day gaps in Phase 2      |
| `timeout_minutes`                  | int  | unlimited | Phase 2 timeout in minutes (1–1440)             |
| `teachers_on_duty`                 | int  | `0`       | TC duty teachers required per slot              |
| `seed`                             | int  | —         | Random seed for Phase 1 reproducibility (debug) |

**Solver configuration note:** CP-SAT runs with `num_workers=1` in production. The free-tier hosting environment (Render) provides a shared fraction of a single vCPU; running multiple parallel workers produces more scheduling overhead than search diversity benefit. If deployed on hardware with ≥4 dedicated vCPUs, increasing `num_workers` would improve optimisation quality.

---

## Project Structure

```
Orarioo/
+-- .github/workflows/        CI/CD: tests, lint, CodeQL, deploy to Render
+-- .githooks/                pre-commit, commit-msg (conventional commits)
+-- doc/                      SVG diagrams, sprint backlog, documentation
+-- src/
    +-- app/                  Django project settings, root URL conf
    +-- common/               Shared utilities (auth, errors, validators, tenancy)
    +-- auditableEntity/      Audit trail: AuditEntry, signals, middleware
    +-- securityIncident/     GDPR security incident log
    +-- namedEntity/          Abstract base with name field
    +-- user/                 Users, collaboration teams, GDPR endpoints
    +-- teacher/              Teacher model (time preferences, weekly hours)
    +-- classroom/            Classroom model (is_shared)
    +-- group/                Student group model (educational stage)
    +-- subject/              Subject model (weekly hours, mandatory classroom)
    +-- schedule/             Core: timetable generation, TC sessions, export
    |   +-- algorithm/
    |   |   +-- generator.py       BasicScheduleGenerator, ScheduleReplanner
    |   |   +-- assignment.py      CP-SAT solver (Phase 1 + Phase 2)
    |   |   +-- slots.py           Weekly slot generation per stage
    |   |   +-- constraints/       hard.py + soft.py
    |   |   +-- tc_assigner.py     TC duty-hour greedy assigner
    |   |   +-- evaluator.py       Post-generation defect detection
    |   |   +-- diagnostics.py     Structured infeasibility diagnostics
    |   |   +-- errors.py          Algorithm-specific exception types
    |   +-- views_generate.py      Generation endpoint
    |   +-- views_move.py          Manual session move endpoint
    |   +-- views_export.py        PDF / Excel export
    |   +-- views_tc.py            TC session CRUD and swap
    +-- main/                 Web interface: templates + static (CSS/JS)
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 15+

### Local setup

```bash
git clone https://github.com/Mialra/Orarioo.git
cd Orarioo
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows
pip install -r src/requirements.txt
```

### Environment variables (`.env`)

```env
SECRET_KEY='your-secret-key'
DB_NAME='orarioo_db'
DB_USER='postgres'
DB_PASSWORD='your-password'
DB_HOST='localhost'
DB_PORT='5432'
ALLOWED_HOSTS='localhost,127.0.0.1'
DEBUG=True
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0
```

### Run

```bash
cd src
python manage.py migrate
python load_test_data.py   # optional: seed with test data
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Tests

```bash
cd src
python manage.py test
# with coverage:
coverage run manage.py test && coverage report
```

### Linting

```bash
cd src
flake8 . && black . && isort .
```

---

## CI/CD

GitHub Actions runs on every push and pull request to `main`:

| Workflow              | What it does                                |
| --------------------- | ------------------------------------------- |
| `django-ci.yml`       | Full Django test suite                      |
| `python-lint.yml`     | Flake8 + Black                              |
| `codeql-analysis.yml` | Static security analysis (weekly + on push) |
| `deploy-render.yml`   | Auto-deploy to Render on merge to `main`    |

---

## Branching Strategy

- `main` — stable, production-ready
- `develop` — integration branch
- `feature/*` — new features
- `fix/*` — bug fixes
- `doc/*` — documentation
