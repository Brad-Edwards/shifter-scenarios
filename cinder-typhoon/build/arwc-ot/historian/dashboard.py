"""Native Grafana PostgreSQL panels with real acquisition-gap markers."""


def trend_sql(series):
    # Only fixed authored series names enter this function.
    if series not in {"level_m", "usable_volume_ml", "position_pct", "position_b_pct", "flow_m3s", "flow_b_m3s", "total_flow_m3s"}:
        raise ValueError("Unknown process series")
    return f'''WITH samples AS (
      SELECT source_time,value,process_quality,lead(source_time) OVER (ORDER BY source_time) AS next_time
      FROM process_history WHERE tag='{series}' AND $__timeFilter(source_time)
    ), points AS (
      SELECT source_time AS time,CASE WHEN process_quality='Good' THEN value ELSE NULL END AS value FROM samples
      UNION ALL SELECT source_time+interval '2 seconds',NULL FROM samples
      WHERE next_time>source_time+interval '2 seconds' OR (next_time IS NULL AND now()>source_time+interval '2 seconds')
    ) SELECT time,value FROM points WHERE $__timeFilter(time) ORDER BY time'''


def dashboard():
    panels = []
    for index, (series, title, unit) in enumerate([
        ("level_m", "Reservoir measured level", "lengthm"), ("usable_volume_ml", "Usable reservoir volume", "megalitres"),
        ("position_pct", "Outlet A measured position", "percent"), ("position_b_pct", "Outlet B measured position", "percent"),
        ("flow_m3s", "Outlet A measured flow", "flowcms"), ("flow_b_m3s", "Outlet B measured flow", "flowcms"),
        ("total_flow_m3s", "Measured total flow", "flowcms"),
    ]):
        panels.append({"id": index+1, "type": "timeseries", "title": title,
            "gridPos": {"x": (index%2)*12, "y": (index//2)*8, "w": 12, "h": 8},
            "datasource": {"type": "postgres", "uid": "arwc-postgres"},
            "targets": [{"refId": "A", "format": "time_series", "rawSql": trend_sql(series)}],
            "fieldConfig": {"defaults": {"unit": unit, "custom": {"spanNulls": False, "drawStyle": "line"}}, "overrides": []}})
    for index, (title, query) in enumerate([
        ("Native alarms and acknowledgements", "SELECT ontime,offtime,acktime,acknowledging_user,text,alarm_group,value,native_status,origin FROM alarm_history WHERE $__timeFilter(ontime) ORDER BY ontime DESC"),
        ("Observed PLC command decisions", "SELECT source_time,channel,decision,sequence,origin,native_status FROM command_history WHERE $__timeFilter(source_time) ORDER BY source_time DESC"),
    ], 8):
        panels.append({"id": index, "type": "table", "title": title,
            "gridPos": {"x": 0, "y": 32+(index-8)*9, "w": 24, "h": 9},
            "datasource": {"type": "postgres", "uid": "arwc-postgres"},
            "targets": [{"refId": "A", "format": "table", "rawSql": query}]})
    return {"uid": "arwc-history", "title": "Cairn Reach process history", "schemaVersion": 41, "version": 2,
        "time": {"from": "now-15m", "to": "now"}, "refresh": "5s", "panels": panels,
        "description": "Native OPC UA acquisition. Gaps and bad process quality remain blank. Command rows are observed PLC decisions, not a complete user audit."}
