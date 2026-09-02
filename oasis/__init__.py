# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
__version__ = "0.1.0"

from oasis.agora_oasis import AgoraOasis, AgoraOasisConfig
from oasis.agora_types import (AssetInput, Observation, PersonaProfile,
                               PlatformPreset, TickResult)
from oasis.data_import import DatasetImporter, ImportReport
from oasis.social_platform.platform import Platform
from oasis.social_platform.typing import ActionType, DefaultPlatformType

__all__ = [
    "make", "Platform", "ActionType", "DefaultPlatformType", "ManualAction",
    "LLMAction", "print_db_contents", "AgentGraph", "SocialAgent", "UserInfo",
    "generate_reddit_agent_graph", "generate_twitter_agent_graph",
    "generate_xiaohongshu_agent_graph",
    "AgoraOasis", "AgoraOasisConfig", "AssetInput", "PersonaProfile",
    "Observation", "TickResult", "DatasetImporter", "ImportReport",
    "PlatformPreset"
]


def __getattr__(name):
    """Lazily load LLM integrations so the base sandbox stays lightweight."""
    if name in {"LLMAction", "ManualAction"}:
        from oasis.environment.env_action import LLMAction, ManualAction
        return {"LLMAction": LLMAction, "ManualAction": ManualAction}[name]
    if name == "make":
        from oasis.environment.make import make
        return make
    if name in {"generate_reddit_agent_graph",
                "generate_twitter_agent_graph",
                "generate_xiaohongshu_agent_graph"}:
        from oasis.social_agent import (generate_reddit_agent_graph,
                                        generate_twitter_agent_graph,
                                        generate_xiaohongshu_agent_graph)
        return {
            "generate_reddit_agent_graph": generate_reddit_agent_graph,
            "generate_twitter_agent_graph": generate_twitter_agent_graph,
            "generate_xiaohongshu_agent_graph":
                generate_xiaohongshu_agent_graph,
        }[name]
    if name == "SocialAgent":
        from oasis.social_agent.agent import SocialAgent
        return SocialAgent
    if name == "AgentGraph":
        from oasis.social_agent.agent_graph import AgentGraph
        return AgentGraph
    if name == "UserInfo":
        from oasis.social_platform.config import UserInfo
        return UserInfo
    if name == "print_db_contents":
        from oasis.testing.show_db import print_db_contents
        return print_db_contents
    raise AttributeError(f"module 'oasis' has no attribute {name!r}")
