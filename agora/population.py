"""Create background accounts inside an experiment, preserving its source world."""

from oasis import PersonaProfile


def extend_population(world, users, count, seed):
    topics = ("城市漫游", "摄影", "咖啡", "数码", "美食", "运动")
    assets = world.db.execute(
        "SELECT DISTINCT pa.asset_id, pa.alt_text, pa.transcript FROM post_asset pa "
        "JOIN post p ON p.post_id=pa.post_id LEFT JOIN community c ON c.name=p.community "
        "WHERE p.visibility='public' AND p.deleted=0 AND p.removed_by IS NULL "
        "AND (c.name IS NULL OR c.visibility='public') ORDER BY pa.asset_id LIMIT 2"
    ).fetchall()
    communities = [
        row[0]
        for row in world.db.execute(
            "SELECT name FROM community WHERE visibility='public' ORDER BY name"
        )
    ]
    result = list(users)
    while len(result) < count:
        index = len(result)
        topic = topics[(index + seed) % len(topics)]
        user = world.add_persona(
            PersonaProfile(
                profile_id=f"background-{seed}-{index}",
                handle=f"sim_{seed % 100000}_{index}",
                display_name=f"{topic}观察员 {index + 1:02d}",
                bio=f"关注{topic}，分享日常，也参与社区讨论。",
                interests={topic: 1.0, topics[(index + seed + 1) % len(topics)]: 0.35},
                posting_probability=0,
            )
        )
        with world.atomic():
            world.db.executemany(
                "INSERT OR IGNORE INTO creator_asset(user_id,asset_id,alt_text,transcript) VALUES (?,?,?,?)",
                [(user, *asset) for asset in assets],
            )
        for community in communities:
            world.join_community(user, community)
        result.append(user)
    return result
