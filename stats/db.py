import sqlite3


def init_db(db_path):
    """
    Initialize DB connection and data tables for metrics and players.

    Args:
        db_path: Local path of the database.

    Returns:
        conn: Connection object.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()

    # server table

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            timestamp INTEGER PRIMARY KEY,

            online INTEGER,

            player_count INTEGER,

            cpu_load REAL,

            ram_used_mb INTEGER,
            ram_max_mb INTEGER,

            threads INTEGER,

            loaded_chunks INTEGER,

            total_joins INTEGER,
            total_deaths INTEGER,

            uptime_ms INTEGER,
            total_runtime_ms INTEGER,
            total_runtime_hms TEXT
        );
    """
    )

    # player table

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS players (
        uuid TEXT PRIMARY KEY,
        name TEXT,

        total_joins INTEGER,
        total_deaths INTEGER,
        total_playtime_ms INTEGER,

        player_kills INTEGER,
        mob_kills INTEGER,
        messages_sent INTEGER,

        advancement_count INTEGER,

        first_join_ts INTEGER,
        last_join_ts INTEGER,
        last_seen_ts INTEGER,

        last_updated_ts INTEGER
    );
    """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(timestamp)")

    conn.commit()
    return conn
