import time


def upsert_player(db_conn, data: dict):
    """
    Insert or update a player's stats in SQLite.

    Args:
        db_conn: SQLite connection
        data: Player JSON payload from MC stats endpoint
    """
    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT INTO players VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(uuid) DO UPDATE SET
            name=excluded.name,
            total_joins=excluded.total_joins,
            total_deaths=excluded.total_deaths,
            total_playtime_ms=excluded.total_playtime_ms,
            player_kills=excluded.player_kills,
            mob_kills=excluded.mob_kills,
            messages_sent=excluded.messages_sent,
            advancement_count=excluded.advancement_count,
            first_join_ts=excluded.first_join_ts,
            last_join_ts=excluded.last_join_ts,
            last_seen_ts=excluded.last_seen_ts,
            last_updated_ts=excluded.last_updated_ts
        """,
        (
            data["uuid"],
            data["name"],
            data["total_joins"],
            data["total_deaths"],
            data["total_playtime_ms"],
            data["player_kills"],
            data["mob_kills"],
            data["messages_sent"],
            data["advancement_count"],
            data["first_join_ts"],
            data["last_join_ts"],
            data["last_seen_ts"],
            int(time.time() * 1000),
        ),
    )
    db_conn.commit()


def get_player_by_name(db_conn, name: str):
    """
    Fetch the most recent stored stats for a player by name.
    """
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT * FROM players
        WHERE LOWER(name) = LOWER(?)
        ORDER BY last_updated_ts DESC
        LIMIT 1
        """,
        (name,),
    )
    return cur.fetchone()
