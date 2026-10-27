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
from PIL import Image

from oasis import AgoraOasis


def test_image_import_and_ordered_post_attachment(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), color=(220, 80, 40)).save(source)

    sandbox = AgoraOasis.local("media-test", data_root=tmp_path / "worlds")
    sandbox.platform.db.execute(
        "INSERT INTO user "
        "(user_id, agent_id, user_name, num_followings, num_followers) "
        "VALUES (1, 1, 'creator', 0, 0)")
    sandbox.platform.db.execute(
        "INSERT INTO post "
        "(post_id, user_id, content, created_at, post_type) "
        "VALUES (1, 1, 'A picture', '0', 'image')")
    sandbox.platform.db.commit()

    media = sandbox.import_media(source)
    sandbox.attach_media(1, media.asset_id, position=0)
    assets = sandbox.get_post_assets(1)

    assert media.media_type == "image"
    assert media.width == 32
    assert media.height == 24
    assert len(media.checksum_sha256) == 64
    assert sandbox.media.path_for(media.object_key).is_file()
    assert assets[0]["asset_id"] == media.asset_id
    assert assets[0]["position"] == 0
    assert assets[0]["role"] == "content"

    sandbox.close()


def test_media_store_rejects_path_traversal(tmp_path):
    sandbox = AgoraOasis.local("path-test", data_root=tmp_path / "worlds")
    try:
        sandbox.media.path_for("../../outside.png")
    except ValueError as exc:
        assert "escapes" in str(exc)
    else:
        raise AssertionError("Path traversal should be rejected.")
    finally:
        sandbox.close()
