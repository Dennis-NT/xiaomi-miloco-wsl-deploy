#!/usr/bin/env python3
"""Patch xiaomi-miloco source after download."""
from pathlib import Path

# 1. lan.py - add MIOT_LAN_TARGETS support
path = Path("miot_kit/miot/lan.py")
text = path.read_text()
text = text.replace(
    "import asyncio\nfrom dataclasses import dataclass\n",
    "import asyncio\nfrom dataclasses import dataclass\nimport os\n"
)
text = text.replace(
    "        self._callbacks_device_status_changed = {}\n\n        self._init_lock = asyncio.Lock()\n",
    "        self._callbacks_device_status_changed = {}\n        self._target_ips = [ip.strip() for ip in os.getenv(\"MIOT_LAN_TARGETS\", \"\").split(\",\") if ip.strip()]\n\n        self._init_lock = asyncio.Lock()\n"
)
text = text.replace(
    "            # Scan devices\n            self.ping_internal()\n",
    "            # Scan devices\n            self.ping_internal()\n            for target_ip in self._target_ips:\n                self.ping_internal(target_ip=target_ip)\n"
)
path.write_text(text)

# 2. client.py - use MIOT_LAN_TARGETS during explicit camera status refresh too
path = Path("miot_kit/miot/client.py")
text = path.read_text()
text = text.replace(
    "import asyncio\nimport logging\nimport time\n",
    "import asyncio\nimport logging\nimport os\nimport time\n"
)
text = text.replace(
    "        await self._lan_client.ping_async()\n        self._last_lan_ping_ts = ts_now\n",
    "        await self._lan_client.ping_async()\n"
    "        for target_ip in [ip.strip() for ip in os.getenv(\"MIOT_LAN_TARGETS\", \"\").split(\",\") if ip.strip()]:\n"
    "            await self._lan_client.ping_async(target_ip=target_ip)\n"
    "        self._last_lan_ping_ts = ts_now\n"
)
path.write_text(text)

# 3. local_mcp_servers.py - FastMCP compat
path = Path("miloco_server/mcp/local_mcp_servers.py")
text = path.read_text()
text = text.replace("on_duplicate_tools=", "on_duplicate=")
text = text.replace('on_duplicate_prompts="error",', '')
text = text.replace('on_duplicate_resources="error",', '')
# Also handle any other on_duplicate_* patterns
text = text.replace('on_duplicate_prompts=', 'on_duplicate=')
text = text.replace('on_duplicate_resources=', 'on_duplicate=')
path.write_text(text)

# 4. mcp.py - FastMCP compat
path = Path("miot_kit/miot/mcp.py")
text = path.read_text()
text = text.replace(
    'on_duplicate_tools="replace",     # Configure behavior for duplicate tool names',
    'on_duplicate="replace",'
)
text = text.replace('on_duplicate_prompts="replace",', '')
text = text.replace('on_duplicate_resources="replace",', '')
path.write_text(text)

# 5. miot_proxy.py - refresh status before get cameras
path = Path("miloco_server/proxy/miot_proxy.py")
text = path.read_text()
text = text.replace(
    "            cameras = await self._miot_client.get_cameras_async()\n",
    "            await self._miot_client.refresh_cameras_status_async()\n            cameras = await self._miot_client.get_cameras_async()\n"
)
path.write_text(text)

# 6. llm_proxy.py - remove temperature
path = Path("miloco_server/proxy/llm_proxy.py")
text = path.read_text()
text = text.replace("temperature=0,", "")
path.write_text(text)

# 7. chat_history_schema.py - add reasoning_content field
path = Path("miloco_server/schema/chat_history_schema.py")
text = path.read_text()
text = text.replace(
    "        self._messages.append(message)",
    '        message["reasoning_content"] = ""\n        self._messages.append(message)'
)
text = text.replace(
    '''    def get_messages(self) -> list[ChatCompletionMessageParam]:
        """
        Get messages
        """
        return self._messages''',
    '''    def get_messages(self) -> list[ChatCompletionMessageParam]:
        """
        Get messages
        """
        for msg in self._messages:
            if msg.get("role") == "assistant" and "reasoning_content" not in msg:
                msg["reasoning_content"] = ""
        return self._messages'''
)
path.write_text(text)

# 8. local_models.py - handle missing local model service
path = Path("miloco_server/utils/local_models.py")
text = path.read_text()
text = text.replace(
    '''    async def local_cuda_info(self):
        """Get local CUDA info."""
        url = self._get_service_url(LocalModelApi.CUDA_INFO)
        json_resp = await self._forward_local_models_services(url, method_get=True)
        return json_resp''',
    '''    async def local_cuda_info(self):
        """Get local CUDA info."""
        try:
            url = self._get_service_url(LocalModelApi.CUDA_INFO)
            json_resp = await self._forward_local_models_services(url, method_get=True)
            return json_resp
        except Exception:
            logger.warning("Local model service not available, returning empty CUDA info")
            return {}'''
)
text = text.replace(
    '''        json_resp = await self._forward_local_models_services(models_url, method_get=True)
        data = json_resp["data"]''',
    '''        try:
            json_resp = await self._forward_local_models_services(models_url, method_get=True)
        except Exception:
            logger.warning("Local model service not available, clearing local model list")
            self._local_models = []
            return
        data = json_resp.get("data")'''
)
path.write_text(text)

print("All patches applied successfully.")
