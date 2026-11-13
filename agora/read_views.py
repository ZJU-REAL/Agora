"""Read old run snapshots through temporary views without rewriting their DB."""


def prepare_read_views(db):
    definitions = {
        "post_asset": {
            "alt_text": "(SELECT m.alt_text FROM main.media_asset m WHERE m.asset_id=original.asset_id)",
            "transcript": "(SELECT m.transcript FROM main.media_asset m WHERE m.asset_id=original.asset_id)",
        },
        "creator_asset": {
            "alt_text": "(SELECT m.alt_text FROM main.media_asset m WHERE m.asset_id=original.asset_id)",
            "transcript": "(SELECT m.transcript FROM main.media_asset m WHERE m.asset_id=original.asset_id)",
        },
        "post": {
            "deleted": "0",
            "removed_by": "NULL",
            "edited_at_tick": "NULL",
            "link_url": "NULL",
        },
        "comment": {"deleted": "0", "edited_at_tick": "NULL"},
        "simulation_state": {
            "current_time_ms": "current_tick * 60000",
            "tick_duration_ms": "60000",
        },
        "agent_model_call": {"decision_id": "NULL", "ordinal": "0"},
    }
    for table, additions in definitions.items():
        present = {row[1] for row in db.execute(f"PRAGMA main.table_info({table})")}
        missing = {key: value for key, value in additions.items() if key not in present}
        if present and missing:
            fields = ",".join(f"{value} AS {name}" for name, value in missing.items())
            db.execute(
                f"CREATE TEMP VIEW {table} AS SELECT original.*,{fields} FROM main.{table} original"
            )
    empty = {
        "community": "NULL AS name,NULL AS title,'' AS description,'[]' AS rules_json,NULL AS creator_id,'public' AS visibility",
        "community_member": "NULL AS community,NULL AS user_id,'member' AS role,0 AS approved",
        "collection_folder": "NULL AS folder_id,NULL AS user_id,'' AS name",
        "folder_post": "NULL AS folder_id,NULL AS post_id",
    }
    for table, columns in empty.items():
        if not db.execute(
            "SELECT 1 FROM main.sqlite_master WHERE name=?", (table,)
        ).fetchone():
            db.execute(f"CREATE TEMP VIEW {table} AS SELECT {columns} WHERE 0")
