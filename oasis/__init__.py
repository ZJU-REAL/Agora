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
"""Agora's native world infrastructure; historical directory name retained."""

__version__ = "0.5.0"
from oasis.agora_types import (
    AssetInput,
    Observation,
    PersonaProfile,
    PlatformPreset,
    TickResult,
)
from oasis.data_import import DatasetImporter, ImportReport
from oasis.world import AgoraWorld, WorldConfig

AgoraOasis = AgoraWorld
AgoraOasisConfig = WorldConfig
__all__ = [
    "AgoraWorld",
    "AssetInput",
    "DatasetImporter",
    "ImportReport",
    "Observation",
    "PersonaProfile",
    "PlatformPreset",
    "TickResult",
    "WorldConfig",
]


def __getattr__(name):
    from importlib import import_module

    legacy = {
        "Platform": ("oasis.legacy.social_platform.platform", "Platform"),
        "make": ("oasis.legacy.environment.make", "make"),
        "LLMAction": ("oasis.legacy.environment.env_action", "LLMAction"),
        "ManualAction": ("oasis.legacy.environment.env_action", "ManualAction"),
        "AgentGraph": ("oasis.legacy.social_agent.agent_graph", "AgentGraph"),
        "SocialAgent": ("oasis.legacy.social_agent.agent", "SocialAgent"),
        "UserInfo": ("oasis.social_platform.config", "UserInfo"),
        "print_db_contents": ("oasis.testing.show_db", "print_db_contents"),
        "ActionType": ("oasis.social_platform.typing", "ActionType"),
        "DefaultPlatformType": ("oasis.social_platform.typing", "DefaultPlatformType"),
    }
    if name.startswith("generate_") and name.endswith("_agent_graph"):
        return getattr(import_module("oasis.legacy.social_agent"), name)
    if name in legacy:
        module, attr = legacy[name]
        return getattr(import_module(module), attr)
    raise AttributeError(name)
