"""Create background accounts inside an experiment, preserving its source world."""

from agora.platform_behavior import relevant_communities
from oasis import PersonaProfile


def extend_population(world, users, count, seed):
    english = world.preset.name in {"x", "reddit"}
    topics = (
        ("photography", "coffee", "technology", "design")
        if english
        else ("城市漫游", "摄影", "咖啡", "数码", "美食", "运动")
    )
    assets = world.db.execute(
        "SELECT DISTINCT pa.asset_id, pa.alt_text, pa.transcript FROM post_asset pa "
        "JOIN post p ON p.post_id=pa.post_id LEFT JOIN community c ON c.name=p.community "
        "WHERE p.visibility='public' AND p.deleted=0 AND p.removed_by IS NULL "
        "AND (c.name IS NULL OR c.visibility='public') ORDER BY pa.asset_id LIMIT 2"
    ).fetchall()
    communities = [
        {"name": row[0], "title": row[1], "description": row[2], "visibility": "public"}
        for row in world.db.execute(
            "SELECT name,title,description FROM community WHERE visibility='public' ORDER BY name"
        )
    ]
    locations = [
        row[0]
        for row in world.db.execute(
            "SELECT DISTINCT location FROM post WHERE visibility='public' AND deleted=0 AND location IS NOT NULL ORDER BY location LIMIT 8"
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
                display_name=f"{topic.title()} reader {index + 1:02d}"
                if english
                else f"{topic}观察员 {index + 1:02d}",
                bio=f"Interested in {topic}. Here to share experiences and learn from discussions."
                if english
                else f"关注{topic}，分享日常，也参与社区讨论。",
                locale="en-US" if english else "zh-CN",
                tone=(("curious",), ("direct",), ("helpful",))[index % 3]
                if english
                else (("简短好奇",), ("具体直接",), ("温和分享",))[index % 3],
                example_posts=(
                    f"One small thing I learned about {topic}: try changing one thing at a time.",
                )
                if english
                else (
                    f"最近关于{topic}的一点新发现。先尝试一个小改变，再看看自己的体验。",
                ),
                interests={topic: 1.0, topics[(index + seed + 1) % len(topics)]: 0.35},
                posting_probability=(0.0, 0.08, 0.03, 0.0)[index % 4],
                like_probability=(0.2, 0.3, 0.1, 0.0)[index % 4],
                comment_probability=(0.05, 0.25, 0.4, 0.01)[index % 4],
                culture={
                    "role": ("reader", "contributor", "questioner", "observer")[
                        index % 4
                    ],
                    **(
                        {"location": locations[index % len(locations)]}
                        if locations and not english
                        else {}
                    ),
                },
            )
        )
        with world.atomic():
            world.db.executemany(
                "INSERT OR IGNORE INTO creator_asset(user_id,asset_id,alt_text,transcript) VALUES (?,?,?,?)",
                [(user, *asset) for asset in assets],
            )
        profile = {
            "interests": {topic: 1.0, topics[(index + seed + 1) % len(topics)]: 0.35}
        }
        for community in relevant_communities(profile, communities)[: 1 + index % 2]:
            world.join_community(user, community["name"])
        result.append(user)
    return result
