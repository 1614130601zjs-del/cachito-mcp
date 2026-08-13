Cachito 全线产品万能 MCP Server
==============================
- 不使用 SSE，纯 HTTP Streamable 传输
- 端点: /mcp
- device_id 通过 getRemoteInfo 实时获取，不硬编码
- 设备类型通过 deviceName 自动匹配模板
- 中文指令变量: 吮吸、入体、脉冲、炮机、抽插、震动、秒潮
- 支持全线产品: 失控2.0/3.0、偷欢/Pro、漫步/Mini/Pro、小猫爪、SK4
- 未知设备自动推断模板

环境变量:
    CACHITO_ACCOUNT: 远程账号 (默认: 52575934)
    PORT: 服务端口 (默认: 8080)
    HOST: 绑定地址 (默认: 0.0.0.0)
"""

import asyncio
import json
import os
import logging
import copy
from typing import Optional

import httpx
import uvicorn
from mcp.server import MCPServer
from mcp.types import TextContent

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("cachito-mcp")

# ==================== 全局配置 ====================
ACCOUNT = os.environ.get("CACHITO_ACCOUNT", "52575934")
API_BASE = "https://www.youtao.top/api/appRemote"

# 中文指令 -> 通道代码映射
CHANNEL_MAP = {
    # 吮吸类
    "吮吸": "sx",
    "吸": "sx",
    "口吸": "sx",
    "吸吮": "sx",
    "秒潮": "sx",
    "舔": "sx",
    # 入体/脉冲类
    "入体": "pj",
    "脉冲": "pj",
    "炮机": "pj",
    "抽插": "pj",
    "震动": "pj",
    "振": "pj",
    "伸缩": "pj",
}

# 设备模板库（以设备名称关键词为 key，device_id 从 API 实时获取后填充）
# 模板中使用占位符: {id_hex2}, {id_hex4}, {intensity_hex}
DEVICE_TEMPLATES = {
    "猫爪": {
        "name": "小猫爪",
        "channels": {
            "sx": {
                "template": "710001{id_hex2}-0400-{id_hex4}-0302-{intensity_hex}00000000",
                "stop": "710001{id_hex2}-0400-{id_hex4}-0601-0200000000",
                "formula": lambda i: round(i * 0.75 + 25),
                "label": "吮吸",
            }
        }
    },
    "失控": {
        "name": "失控",
        "channels": {
            "sx": {
                "template": "710002{id_hex2}-0400-{id_hex4}-0302-{intensity_hex}00000000",
                "stop": "710002{id_hex2}-0400-{id_hex4}-0302-0000000000",
                "formula": lambda i: round(i * 0.75 + 25),
                "label": "吮吸",
            },
            "pj": {
                "template": "710002{id_hex2}-0400-{id_hex4}-050A-{intensity_hex}00000000",
                "stop": "710002{id_hex2}-0400-{id_hex4}-0601-0000000000",
                "formula": lambda i: round(i * 0.75 + 25),
                "label": "脉冲/入体",
            }
        }
    },
    "偷欢": {
        "name": "偷欢",
        "channels": {
            "sx": {
                "template": "71000C{id_hex2}-8200-{id_hex4}-0100-{intensity_hex}000002",
                "stop": "71000C{id_hex2}-0F00-{id_hex4}-0100-0000000000",
                "formula": lambda i: round(i * 0.5 + 50),
                "label": "吮吸",
            }
        }
    },
    "漫步": {
        "name": "漫步",
        "channels": {
            "sx": {
                "template": "710017{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
                "stop": "710017{id_hex2}-0100-{id_hex4}-0100-6400000002",
                "formula": lambda i: round(i * 0.5 + 50),
                "label": "吮吸",
            }
        }
    },
    "SK": {
        "name": "SK",
        "channels": {
            "sx": {
                "template": "710017{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
                "stop": "710017{id_hex2}-0100-{id_hex4}-0100-6400000002",
                "formula": lambda i: round(i * 0.5 + 50),
                "label": "吮吸",
            }
        }
    },
}

# 通用回退模板（当设备名称完全无法识别时使用）
GENERIC_TEMPLATE = {
    "name": "通用设备",
    "channels": {
        "sx": {
            "template": "7100{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
            "stop": "7100{id_hex2}-0100-{id_hex4}-0100-6400000002",
            "formula": lambda i: round(i * 0.5 + 50),
            "label": "吮吸（通用）",
        }
    }
}


# ==================== API 交互层 ====================

async def api_post(client: httpx.AsyncClient, endpoint: str, payload: dict) -> dict:
    """统一 API 请求封装"""
    try:
        resp = await client.post(
            f"{API_BASE}/{endpoint}",
            json=payload,
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"API [{endpoint}] 错误: {e}")
        return {"code": -1, "message": str(e)}


async def get_device_info(client: httpx.AsyncClient, code: str):
    """
    通过 getRemoteInfo 获取设备信息
    返回: (device_id, device_name, error_message, raw_data)
    """
    data = await api_post(client, "getRemoteInfo", {"account": ACCOUNT, "code": code})
    if data.get("code") != 0:
        return None, None, data.get("message", "获取设备信息失败"), data

    remote = data.get("data", {}).get("remote", {})
    device_id = remote.get("deviceId")
    device_name = remote.get("deviceName", "未知设备")

    if device_id is None:
        return None, None, "未获取到设备ID", data

    logger.info(f"getRemoteInfo 返回: {device_name} (ID={device_id})")
    return device_id, device_name, None, remote


def resolve_device_config(device_name: str) -> tuple[dict, str]:
    """
    根据设备名称自动匹配模板
    返回: (config_dict, matched_keyword)
    """
    name_upper = (device_name or "").upper()

    for keyword, tmpl in DEVICE_TEMPLATES.items():
        if keyword.upper() in name_upper:
            cfg = copy.deepcopy(tmpl)
            cfg["name"] = device_name
            return cfg, keyword

    # 完全未知，使用通用模板
    logger.warning(f"设备 '{device_name}' 未匹配到已知模板，使用通用吮吸模板")
    cfg = copy.deepcopy(GENERIC_TEMPLATE)
    cfg["name"] = device_name
    return cfg, "通用"


def inject_device_id(cfg: dict, device_id: int) -> dict:
    """将 device_id 注入模板占位符"""
    h2 = format(device_id, "02x")
    h4 = format(device_id, "04x")
    for ch in cfg.get("channels", {}).values():
        for key in ("template", "stop"):
            if key in ch:
                ch[key] = ch[key].replace("{id_hex2}", h2).replace("{id_hex4}", h4)
    return cfg


def resolve_channel(cfg: dict, user_channel: str):
    """
    解析用户输入的通道（支持中文/英文/别名）
    返回: (channel_code, error_message)
    """
    ch = user_channel.strip().lower()
    channels = cfg.get("channels", {})

    # 直接匹配通道代码
    if ch in channels:
        return ch, None

    # 中文映射表匹配
    if ch in CHANNEL_MAP:
        mapped = CHANNEL_MAP[ch]
        if mapped in channels:
            return mapped, None
        available = [f"{k}({v['label']})" for k, v in channels.items()]
        return None, f"该设备不支持 '{user_channel}'，可用功能: {', '.join(available)}"

    # 模糊匹配标签
    for code, info in channels.items():
        label = info.get("label", "").lower()
        if ch in label or label in ch:
            return code, None

    available = [f"{k}({v['label']})" for k, v in channels.items()]
    return None, f"无法识别 '{user_channel}'，可用功能: {', '.join(available)}"


async def join_remote(client: httpx.AsyncClient, code: str) -> Optional[str]:
    """加入远程控制会话"""
    data = await api_post(client, "joinRemote", {"account": ACCOUNT, "code": code})
    if data.get("code") != 0:
        return data.get("message", "加入远程失败")
    return None


async def send_command(
    client: httpx.AsyncClient,
    code: str,
    device_id: int,
    cfg: dict,
    channel: str,
    action: str,
    intensity: int,
    duration: int,
) -> dict:
    """发送设备控制指令"""
    ch_cfg = cfg["channels"][channel]

    if action == "stop":
        cmd = ch_cfg["stop"]
        time_ms = 500
        desc = "停止"
    else:
        val = max(0, min(100, intensity))
        hex_val = format(ch_cfg["formula"](val), "02x")
        cmd = ch_cfg["template"].replace("{intensity_hex}", hex_val)
        time_ms = max(500, duration)
        desc = f"强度{val}%"

    payload = json.dumps([{"command": cmd, "time": str(time_ms), "progress": 0}])
    cmd_key = "pjCommand" if channel == "pj" else "sxCommand"

    result = await api_post(client, "sendCommand", {
        "command": {cmd_key: payload, "deviceId": device_id},
        "account": ACCOUNT,
        "code": code,
    })

    if result.get("code") == 0:
        return {
            "success": True,
            "device": cfg["name"],
            "deviceId": device_id,
            "channel": channel,
            "channelLabel": ch_cfg["label"],
            "action": action,
            "intensity": intensity if action != "stop" else 0,
            "duration": time_ms,
            "command": cmd,
            "message": f"{cfg['name']} {ch_cfg['label']} 已{desc}",
        }
    else:
        return {
            "success": False,
            "error": result.get("message", "发送指令失败"),
            "detail": result,
        }


# ==================== MCP Server 定义 ====================

server = MCPServer("cachito-universal-mcp")


@server.tool(
    name="toy_control",
    description="控制 Cachito 全线情趣玩具设备。自动通过getRemoteInfo获取设备ID并匹配模板，支持中文指令：吮吸、入体、脉冲、炮机、抽插、震动、秒潮等。",
)
async def toy_control(
    code: str,
    action: str = "vibrate",
    channel: str = "吮吸",
    intensity: int = 50,
    duration: int = 3000,
) -> str:
    """
    控制 Cachito 设备

    Args:
        code: 设备远程分享码（从 Cachito APP 获取）
        action: 动作 - vibrate/start 启动，stop 停止
        channel: 功能通道，支持中文：吮吸、入体、脉冲、炮机、抽插、震动、秒潮等
        intensity: 强度 0-100
        duration: 持续时间（毫秒），默认 3000
    """
    async with httpx.AsyncClient() as client:
        # 1. 通过 getRemoteInfo 实时获取 device_id 和 device_name
        dev_id, dev_name, err, _ = await get_device_info(client, code)
        if err:
            return json.dumps({"success": False, "error": f"获取设备失败: {err}"}, ensure_ascii=False)

        # 2. 根据 device_name 自动匹配模板（不依赖硬编码 id）
        cfg, matched_kw = resolve_device_config(dev_name)

        # 3. 将获取到的 device_id 注入模板
        cfg = inject_device_id(cfg, dev_id)

        # 4. 解析通道（中文自动映射）
        ch, err = resolve_channel(cfg, channel)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)

        # 5. 加入远程
        err = await join_remote(client, code)
        if err:
            return json.dumps({"success": False, "error": f"加入远程失败: {err}"}, ensure_ascii=False)

        # 6. 发送指令
        result = await send_command(
            client, code, dev_id, cfg, ch,
            "stop" if action == "stop" else "vibrate",
            intensity, duration,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


@server.tool(
    name="list_devices",
    description="查询指定设备码对应的设备信息（通过getRemoteInfo实时获取ID）和可用功能列表",
)
async def list_devices(code: str) -> str:
    """
    查询设备信息

    Args:
        code: 设备远程分享码
    """
    async with httpx.AsyncClient() as client:
        dev_id, dev_name, err, remote = await get_device_info(client, code)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)

        cfg, matched_kw = resolve_device_config(dev_name)
        cfg = inject_device_id(cfg, dev_id)

        return json.dumps({
            "success": True,
            "deviceId": dev_id,
            "deviceName": dev_name,
            "matchedTemplate": matched_kw,
            "channels": {
                k: {"name": v["label"], "code": k}
                for k, v in cfg["channels"].items()
            },
            "account": ACCOUNT,
        }, ensure_ascii=False, indent=2)


@server.tool(
    name="discover_devices",
    description="获取所有支持的 Cachito 设备类型清单和指令别名",
)
async def discover_devices() -> str:
    """获取支持的设备清单"""
    devices = []
    for keyword, cfg in DEVICE_TEMPLATES.items():
        devices.append({
            "keyword": keyword,
            "name": cfg["name"],
            "channels": [
                {"code": k, "name": v["label"]}
                for k, v in cfg["channels"].items()
            ],
        })

    return json.dumps({
        "success": True,
        "note": "device_id 通过 getRemoteInfo 实时获取，不在此硬编码",
        "totalTypes": len(devices),
        "devices": devices,
        "channelAliases": CHANNEL_MAP,
    }, ensure_ascii=False, indent=2)


# ==================== Starlette App (Streamable HTTP, 非 SSE) ====================
# 关键: streamable_http_app 使用纯 HTTP，不需要 SSE
# 端点: /mcp

app = server.streamable_http_app(streamable_http_path="/mcp")

# ==================== 启动入口 ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"Cachito Universal MCP (Streamable HTTP) running at http://{host}:{port}/mcp")
    uvicorn.run(app, host=host, port=port)
