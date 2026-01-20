import aiohttp
import time


async def poll_stats(db_conn, url, token):
    """
    Makes an API call to the minecraft server using the token and appends
    instantaneous server statistics to SQLite DB.

    Args:
        db_conn: SQLite DB connection object.
        url: Server endpoint to fetch.
        token: Secure token for authentication.
    """
    ts = int(time.time() * 1000)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"X-Stats-Token": token},
                timeout=2,
            ) as resp:
                data = await resp.json()

        row = (
            ts,  # timestamp
            1,  # online
            data["player_count"],  # player_count
            data["cpu_load"],  # cpu_load
            data["ram_used_mb"],  # ram_used_mb
            data["ram_max_mb"],  # ram_max_mb
            data["threads"],  # threads
            data["loaded_chunks"],  # loaded_chunks
            data["total_joins"],  # total_joins
            data["total_deaths"],  # total_deaths
            data["uptime_ms"],  # uptime_ms
            data["total_runtime_ms"],  # total_runtime_ms
            data["total_runtime_hms"],  # total_runtime_hms
        )

        # print("[STATS] polled at", ts)

    except Exception as e:
        # print("Server offline")
        row = (
            ts,  # timestamp
            0,  # online
            0,  # player_count
            0.0,  # cpu_load
            0,  # ram_used_mb
            0,  # ram_max_mb
            0,  # threads
            0,  # loaded_chunks
            0,  # total_joins
            0,  # total_deaths
            0,  # uptime_ms
            0,  # total_runtime_ms
            "00h 00m 00s",  # total_runtime_hms
        )

    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO metrics VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        row,
    )
    db_conn.commit()
