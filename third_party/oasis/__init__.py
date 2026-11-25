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
"""Archived OASIS-derived integrations; not used by the Agora runtime."""


def __getattr__(name):
    from importlib import import_module

    exports = {
        "Platform": ("social_platform.platform", "Platform"),
        "make": ("environment.make", "make"),
        "LLMAction": ("environment.env_action", "LLMAction"),
        "ManualAction": ("environment.env_action", "ManualAction"),
        "AgentGraph": ("social_agent.agent_graph", "AgentGraph"),
        "SocialAgent": ("social_agent.agent", "SocialAgent"),
        "UserInfo": ("social_platform.config", "UserInfo"),
        "print_db_contents": ("testing.show_db", "print_db_contents"),
        "ActionType": ("social_platform.typing", "ActionType"),
        "DefaultPlatformType": ("social_platform.typing", "DefaultPlatformType"),
    }
    if name.startswith("generate_") and name.endswith("_agent_graph"):
        return getattr(import_module("third_party.oasis.social_agent"), name)
    if name in exports:
        module, attr = exports[name]
        return getattr(import_module("third_party.oasis." + module), attr)
    raise AttributeError(name)
