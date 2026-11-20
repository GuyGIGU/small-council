# Stack — Chrollo
<!-- Illustrative example of the book's stack page (references/templates/stack.md) for the fictional Chrollo
     service in council.config.md beside it. Watch lists name the checklist pages of references/watch-lists.md
     for each part, analogous ones included (a pandas engine takes quality-llm's numerical rules). -->

| Kind | What | Reason | Since | Watch lists |
|---|---|---|---|---|
| language | Python 3.12 | the team's language, and the numerical libraries it needs | before setup | refactoring, quality-testing |
| library | pandas · numpy · scipy | a deterministic engine whose output must stay byte-identical | before setup | quality-llm, quality-performance |
| framework | FastAPI + Uvicorn | a small local API for the web app | before setup | quality-backend, security |
| library | SQLAlchemy over SQLite, a parquet cache | one host, no server to run | before setup | quality-postgres |
| framework | React 19 + Vite (plain JSX) | not recorded | before setup | quality-frontend, quality-ux |
| tool | pytest, the recall and shadow-parity harnesses | the shadow corpus proves the engine's output unchanged | before setup | quality-testing |
| service | the broker link (read-only) | the screener's market data | before setup | untrusted-input, quality-operability |
