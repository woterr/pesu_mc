import matplotlib.pyplot as plt
import sqlite3
from datetime import datetime
import time


def plot_metric(db_conn, metric, minutes=60, ylabel="", multiply=1.0):
    """
    Produce a graph for the requested metric and time.

    Args:
        metric: Column name in metrics table.
        minutes: How far back to plot.
        multiply: Scale factor (e.g. cpu_load * 100).

    Returns:
        str: File path of the saved image. (MUST BE DELETED AFTER SENDING TO USER)
    """

    cur = db_conn.cursor()
    since = int((time.time() - minutes * 60) * 1000)
    cur.execute(
        f"""
        SELECT timestamp, {metric}
        FROM metrics
        WHERE timestamp >= ?
        AND online = 1
        ORDER BY timestamp
        """,
        (since,),
    )

    rows = cur.fetchall()
    if not rows:
        return None

    times = [datetime.fromtimestamp(ts / 1000) for ts, _ in rows]
    values = [v * multiply for _, v in rows]

    plt.figure(figsize=(8, 4))
    plt.plot(times, values)
    plt.xlabel("Time")
    plt.ylabel(ylabel or metric)
    plt.title(
        f"{metric.replace('_', ' ').title()} "
        f"(last {minutes} min, {len(values)} points)"
    )
    plt.tight_layout()

    filename = f"/tmp/{metric}_{int(datetime.utcnow().timestamp())}.png"
    plt.savefig(filename)
    plt.close()

    return filename
