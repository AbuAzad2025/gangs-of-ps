# Critical Development Rules

1. **Database**: STRICTLY PostgreSQL. Use JSON/JSONB types. Avoid SQLite patterns.
2. **Translation**: ALWAYS update `messages.po` and run `pybabel compile` immediately for ANY new text.
3. **Consistency**: Verify logic alignment. Ensure new code matches existing patterns.
4. **No Duplication**: EXTEND existing routes/modules. NEVER create redundant files or functions.
5. **Admin Panel**: IMMEDIATELY expose new features/settings in the Developer/Admin panel.
6. **Concurrency & Scale**: Use atomic DB transactions (`db.session.begin_nested()`, `with_for_update()`) and handle race conditions. The game must support thousands of concurrent users.
