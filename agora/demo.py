"""Small synthetic world for exercising feeds, account tools and replay."""

from __future__ import annotations


def populate(world):
    if world.db.execute("SELECT COUNT(*) FROM user").fetchone()[0]:
        raise ValueError("Demo requires an empty world; use a new world_id")
    # Persona and media construction belong to the transitional backend.
    from PIL import Image, ImageDraw

    from oasis import AssetInput, PersonaProfile

    topics = ["城市漫游", "咖啡", "摄影", "数码", "美食", "运动"]
    names = ["沿途记录", "咖啡手记", "光影之间", "数码日常", "一人食记", "慢跑计划"]
    users = []
    for index, (topic, name) in enumerate(zip(topics, names)):
        users.append(
            world.add_persona(
                PersonaProfile(
                    profile_id=f"demo-{index}",
                    handle=f"creator_{index}",
                    display_name=name,
                    bio=f"记录日常里的{topic}，分享体验，也听听不同的想法。",
                    interests={topic: 1.0, topics[(index + 1) % len(topics)]: 0.3},
                    posting_probability=0,
                )
            )
        )
    colors = [
        (65, 101, 88),
        (151, 102, 75),
        (97, 115, 155),
        (66, 90, 112),
        (174, 114, 100),
        (111, 135, 81),
    ]
    titles = [
        "周末换条路，发现城市的另一面",
        "试了三种冲法，终于找到喜欢的味道",
        "普通街角也能拍出喜欢的照片",
        "用了两周，再聊聊这件小装备",
        "工作日也能认真吃饭",
        "从十分钟开始，慢慢找到自己的节奏",
    ]
    for index in range(48):
        author_index = index % len(users)
        topic, color = topics[author_index], colors[author_index]
        image = Image.new("RGB", (600, 750), color)
        draw = ImageDraw.Draw(image)
        # Code-rendered synthetic covers require no downloads or generated assets.
        draw.ellipse((80, 100, 510, 530), fill=tuple(min(255, c + 35) for c in color))
        draw.rectangle((50, 490, 550, 640), fill=tuple(max(0, c - 25) for c in color))
        draw.text((80, 560), f"AGORA / {index + 1:02d}", fill="white")
        path = world.config.world_dir / "demo-cover.png"
        image.save(path)
        world.create_post(
            users[author_index],
            title=f"{titles[author_index]} · {index // 6 + 1}",
            body=f"今天记录一段关于{topic}的真实体验。这是合成演示内容。"
            "有些尝试很顺利，也有些需要调整。你会怎么做？欢迎分享自己的经验。",
            post_type="image",
            assets=[AssetInput(path, alt_text=f"{topic}主题的合成色块封面")],
            topics=[topic],
            language="zh-CN",
        )
        path.unlink()
    reader = world.add_persona(
        PersonaProfile(
            "demo-reader",
            "reader",
            "周末观察员",
            bio="喜欢城市漫游、摄影，也会看咖啡分享。",
            interests={"城市漫游": 1.0, "摄影": 0.7, "咖啡": 0.3},
            posting_probability=0,
        )
    )
    world.follow_user(reader, users[0])
    assets = world.db.execute(
        "SELECT asset_id FROM creator_asset WHERE user_id = ? ORDER BY asset_id LIMIT 3",
        (users[0],),
    ).fetchall()
    world.db.executemany(
        "INSERT OR IGNORE INTO creator_asset(user_id, asset_id) VALUES (?, ?)",
        [(reader, row[0]) for row in assets],
    )
    world.db.commit()
    world.set_seed(42)
    return {
        "reader_id": reader,
        "creator_ids": users,
        "world_id": world.config.world_id,
        "posts": 48,
    }
