# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
import asyncio
import json

from oasis.social_platform.platform import Platform


def test_threaded_comments_preserve_root_and_reply_target(tmp_path):
    db_path = tmp_path / "threaded_comments.db"
    platform = Platform(str(db_path))

    platform.db.executemany(
        "INSERT INTO user "
        "(user_id, agent_id, user_name, num_followings, num_followers) "
        "VALUES (?, ?, ?, 0, 0)",
        [(1, 1, "alice"), (2, 2, "bob"), (3, 3, "carol")],
    )
    platform.db.execute(
        "INSERT INTO post (post_id, user_id, content, created_at) "
        "VALUES (1, 1, 'A post', '0')")
    platform.db.commit()

    root = asyncio.run(
        platform.create_comment(2, (1, "Top-level comment")))
    reply = asyncio.run(
        platform.create_comment(1,
                                (1, "Reply to Bob", root["comment_id"])))
    nested_reply = asyncio.run(
        platform.create_comment(
            3, (1, "Reply to Alice", reply["comment_id"])))

    assert root == {
        "success": True,
        "comment_id": 1,
        "parent_comment_id": None,
        "root_comment_id": 1,
        "reply_to_user_id": None,
    }
    assert reply["root_comment_id"] == root["comment_id"]
    assert reply["reply_to_user_id"] == 2
    assert nested_reply["root_comment_id"] == root["comment_id"]
    assert nested_reply["reply_to_user_id"] == 1

    rows = platform.db.execute(
        "SELECT comment_id, parent_comment_id, root_comment_id, "
        "reply_to_user_id FROM comment ORDER BY comment_id").fetchall()
    assert rows == [(1, None, 1, None), (2, 1, 1, 2), (3, 2, 1, 1)]

    trace = platform.db.execute(
        "SELECT info FROM trace WHERE action = 'create_comment'").fetchall()
    assert len(trace) == 3
    trace_by_comment = {
        item["comment_id"]: item for item in (json.loads(row[0]) for row in trace)
    }
    assert trace_by_comment[3]["parent_comment_id"] == 2

    platform.db_cursor.close()
    platform.db.close()


def test_reply_rejects_parent_from_another_post(tmp_path):
    db_path = tmp_path / "invalid_thread.db"
    platform = Platform(str(db_path))
    platform.db.execute(
        "INSERT INTO user "
        "(user_id, agent_id, user_name, num_followings, num_followers) "
        "VALUES (1, 1, 'alice', 0, 0)")
    platform.db.executemany(
        "INSERT INTO post (post_id, user_id, content, created_at) "
        "VALUES (?, 1, ?, '0')", [(1, "First"), (2, "Second")])
    platform.db.commit()

    root = asyncio.run(platform.create_comment(1, (1, "On first post")))
    invalid = asyncio.run(
        platform.create_comment(
            1, (2, "Wrong thread", root["comment_id"])))

    assert invalid == {
        "success": False,
        "error": "Parent comment belongs to another post.",
    }
    count = platform.db.execute(
        "SELECT COUNT(*) FROM comment").fetchone()[0]
    assert count == 1

    platform.db_cursor.close()
    platform.db.close()
