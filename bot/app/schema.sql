PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Группа учеников. Ведёт её один или несколько менторов.
CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    start_date  TEXT,                     -- ISO дата дня 1
    lesson_time TEXT,                     -- HH:MM, ручной override времени (редко нужен)
    shift       TEXT NOT NULL DEFAULT 'evening',  -- morning | evening, см. course.yaml:shifts
    format      TEXT,                     -- online | offline | NULL (неизвестно); на расписание не влияет
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Ученики
CREATE TABLE IF NOT EXISTS students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id     INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    full_name    TEXT NOT NULL,
    short_name   TEXT,
    class_school TEXT,
    team         TEXT,
    phone        TEXT,                    -- из колонки «Контакты» ростера, для детского бота
    tg_user_id   INTEGER,                  -- привязка к аккаунту в детском боте (см. app/kids)
    active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(group_id, full_name)
);
-- Индекс на tg_user_id ставится только в app/db.py:_migrate(), НЕ здесь: на
-- существующей базе (до миграции) колонки ещё нет, а executescript() гоняет
-- этот файл целиком при каждом старте — CREATE INDEX на несуществующую
-- колонку уронит запуск. Для новых баз колонка уже есть в CREATE TABLE выше,
-- миграция всё равно создаёт индекс идемпотентно (IF NOT EXISTS).

-- Отзывы учеников о занятии — детский бот. Анонимны ПО ПОЛИТИКЕ: student_id
-- хранится (нужен для дедупликации «уже отвечал сегодня» и для будущих
-- разборов), но ни один экран для менторов/админа не должен присоединять
-- имя ученика к тексту отзыва — см. app/db.py: group_kid_feedback().
CREATE TABLE IF NOT EXISTS kid_feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    group_id   INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    day_index  INTEGER NOT NULL,
    rating     INTEGER,                    -- 1..5, необязательно
    text       TEXT,
    source     TEXT NOT NULL DEFAULT 'text',  -- text | voice
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_kid_feedback_group_day ON kid_feedback(group_id, day_index);

-- Команды на хакатон. Заполняются учениками через детского бота (капитан
-- создаёт, остальные присоединяются по ссылке-коду) — это и заполняет
-- students.team в менторской базе, без ручного ввода составов админом.
-- Кросс-групповые команды сейчас разрешены намеренно (сузить — отдельная
-- задача на будущее).
CREATE TABLE IF NOT EXISTS hack_teams (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    case_name  TEXT,
    leader_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    join_code  TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS hack_team_members (
    team_id    INTEGER NOT NULL REFERENCES hack_teams(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    joined_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, student_id)
);

-- Белый список телефонов: кто имеет право зарегистрироваться ментором.
-- Заполняется админом до старта курса (CSV или /add_mentor).
CREATE TABLE IF NOT EXISTS roster (
    phone     TEXT PRIMARY KEY,           -- только цифры, без '+'
    full_name TEXT NOT NULL,
    group_id  INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    is_admin  INTEGER NOT NULL DEFAULT 0,
    is_mentor INTEGER NOT NULL DEFAULT 1   -- из Excel: роль "админ" без "ментор" даёт 0
);

-- Зарегистрированные менторы. is_admin и is_mentor независимы: бывает
-- только организатор без своей группы (is_admin=1, is_mentor=0), обычный
-- ментор (is_mentor=1), и то и другое сразу (первый bootstrap-пользователь).
CREATE TABLE IF NOT EXISTS mentors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL UNIQUE,
    phone      TEXT,
    full_name  TEXT,
    is_admin   INTEGER NOT NULL DEFAULT 0,
    is_mentor  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mentor_groups (
    mentor_id INTEGER NOT NULL REFERENCES mentors(id) ON DELETE CASCADE,
    group_id  INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (mentor_id, group_id)
);

-- Заполнение чек-листа за конкретный день
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mentor_id   INTEGER NOT NULL REFERENCES mentors(id) ON DELETE CASCADE,
    group_id    INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    day_index   INTEGER NOT NULL,         -- 1..9, 0 = финальный опрос
    kind        TEXT NOT NULL DEFAULT 'lesson',  -- lesson | final
    status      TEXT NOT NULL DEFAULT 'open',    -- open | done | abandoned
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_group_day ON sessions(group_id, day_index, kind);

-- Ответы. Один ряд = один ответ на один вопрос.
CREATE TABLE IF NOT EXISTS answers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    group_id     INTEGER NOT NULL,
    day_index    INTEGER NOT NULL,
    student_id   INTEGER REFERENCES students(id) ON DELETE CASCADE,  -- NULL = вопрос по группе
    question_key TEXT NOT NULL,
    question_text TEXT,
    maps_to      TEXT,
    value        TEXT,                    -- нормализованное значение (число/код варианта)
    text         TEXT,                    -- человекочитаемый ответ
    source       TEXT NOT NULL DEFAULT 'text',  -- text | voice | button | skip
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_answers_student ON answers(student_id);
CREATE INDEX IF NOT EXISTS idx_answers_session ON answers(session_id);

-- Сгенерированные характеристики
CREATE TABLE IF NOT EXISTS characteristics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    payload    TEXT NOT NULL,             -- JSON от LLM
    html_path  TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Чтобы не слать одно и то же напоминание дважды
CREATE TABLE IF NOT EXISTS notifications (
    key        TEXT PRIMARY KEY,
    sent_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Пригласительные ссылки: t.me/<bot>?start=inv_<token> (менторы, админы —
-- этот бот) или t.me/<kids_bot>?start=inv_<token> (ученики — детский бот).
-- Групповая (student_id IS NULL, role='mentor') — многоразовая, пока не
-- отозвана (revoked=1). Персональная (student_id задан) — одноразовая:
-- used_by_tg/used_at ставятся при первом использовании, дальше её отвергают
-- (кроме повторного захода того же used_by_tg — это просто открыть свой
-- обычный экран заново, не ошибка).
CREATE TABLE IF NOT EXISTS invites (
    token      TEXT PRIMARY KEY,
    group_id   INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'mentor',
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked    INTEGER NOT NULL DEFAULT 0,
    used_by_tg INTEGER,
    used_at    TEXT
);
