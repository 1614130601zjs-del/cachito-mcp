#!/usr/bin/env python3
import json, os, logging, copy
from typing import Optional
import httpx, uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cachito-mcp")

ACCOUNT = os.environ.get("CACHITO_ACCOUNT", "52575934")
API_BASE = "https://www.youtao.top/api/appRemote"

CHANNEL_MAP = {
    "吮吸": "sx", "吸": "sx", "口吸": "sx", "秒潮": "sx", "舔": "sx",
    "入体": "pj", "脉冲": "pj", "炮机": "pj", "抽插": "pj", "震动": "pj", "振": "pj", "伸缩": "pj",
}

DEVICE_TEMPLATES = {
    "猫爪": {
        "channels": {
            "sx": {"template": "710001{id_hex2}-0400-{id_hex4}-0302-{intensity_hex}00000000",
                   "stop": "710001{id_hex2}-0400-{id_hex4}-0601-0200000000",
                   "formula": lambda i: round(i * 0.75 + 25), "label": "吮吸"}
        }
    },
    "失控": {
        "channels": {
            "sx": {"template": "710002{id_hex2}-0400-{id_hex4}-0302-{intensity_hex}00000000",
                   "stop": "710002{id_hex2}-0400-{id_hex4}-0302-0000000000",
                   "formula": lambda i: round(i * 0.75 + 25), "label": "吮吸"},
            "pj": {"template": "710002{id_hex2}-0400-{id_hex4}-050A-{intensity_hex}00000000",
                   "stop": "710002{id_hex2}-0400-{id_hex4}-0601-0000000000",
                   "formula": lambda i: round(i * 0.75 + 25), "label": "脉冲/入体"}
        }
    },
    "偷欢": {
        "channels": {
            "sx": {"template": "71000C{id_hex2}-8200-{id_hex4}-0100-{intensity_hex}000002",
                   "stop": "71000C{id_hex2}-0F00-{id_hex4}-0100-0000000000",
                   "formula": lambda i: round(i * 0.5 + 50), "label": "吮吸"}
        }
    },
    "漫步": {
        "channels": {
            "sx": {"template": "710017{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
                   "stop": "710017{id_hex2}-0100-{id_hex4}-0100-6400000002",
                   "formula": lambda i: round(i * 0.5 + 50), "label": "吮吸"}
        }
    },
    "SK": {
        "channels": {
            "sx": {"template": "710017{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
                   "stop": "710017{id_hex2}-0100-{id_hex4}-0100-6400000002",
                   "formula": lambda i: round(i * 0.5 + 50), "label": "吮吸"}
        }
    },
}

GENERIC = {
    "channels": {
        "sx": {"template": "7100{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
               "stop": "7100{id_hex2}-0100-{id_hex4}-0100-6400000002",
               "formula": lambda i: round(i * 0.5 + 50), "label": "吮吸（通用）"}
    }
}

async def api_post(client, endpoint, payload):
    try:
        r = await client.post(f"{API_BASE}/{endpoint}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"API [{endpoint}] {e}")
        return {"code": -1, "message": str(e)}

async def get_device_info(client, code):
    data = await api_post(client, "getRemoteInfo", {"account": ACCOUNT, "code": code})
    if data.get("code") != 0:
        return None, None, data.get("message", "获取失败")
    remote = data.get("data", {}).get("remote", {})
    dev_id = remote.get("deviceId")
    dev_name = remote.get("deviceName", "未知")
    if dev_id is None:
        return None, None, "无设备ID"
    logger.info(f"设备: {dev_name} (ID={dev_id})")
    return dev_id, dev_name, None

def match_config(name):
    up = (name or "").upper()
    for kw, tmpl in DEVICE_TEMPLATES.items():
        if kw.upper() in up:
            cfg = copy.deepcopy(tmpl)
            cfg["name"] = name
            return cfg, kw
    logger.warning(f"'{name}' 未匹配，使用通用模板")
    cfg = copy.deepcopy(GENERIC)
    cfg["name"] = name
    return cfg, "通用"

def inject_id(cfg, dev_id):
    h2, h4 = format(dev_id, "02x"), format(dev_id, "04x")
    for ch in cfg.get("channels", {}).values():
        for k in ("template", "stop"):
            if k in ch:
                ch[k] = ch[k].replace("{id_hex2}", h2).replace("{id_hex4}", h4)
    return cfg

def resolve_ch(cfg, user_ch):
    ch = user_ch.strip().lower()
    channels = cfg.get("channels", {})
    if ch in channels:
        return ch, None
    if ch in CHANNEL_MAP:
        m = CHANNEL_MAP[ch]
        if m in channels:
            return m, None
        return None, f"不支持'{user_ch}'，可用: {', '.join(f'{k}({v[\"label\"]})' for k,v in channels.items())}"
    for code, info in channels.items():
        if ch in info["label"].lower() or info["label"].lower() in ch:
            return code, None
    return None, f"无法识别'{user_ch}'，可用: {', '.join(f'{k}({v[\"label\"]})' for k,v in channels.items())}"

async def join(client, code):
    data = await api_post(client, "joinRemote", {"account": ACCOUNT, "code": code})
    if data.get("code") != 0:
        return data.get("message", "加入失败")
    return None

async def send_cmd(client, code, dev_id, cfg, ch, action, intensity, duration):
    c = cfg["channels"][ch]
    if action == "stop":
        cmd, time_ms, desc = c["stop"], 500, "停止"
    else:
        v = max(0, min(100, intensity))
        cmd = c["template"].replace("{intensity_hex}", format(c["formula"](v), "02x"))
        time_ms, desc = max(500, duration), f"强度{v}%"
    payload = json.dumps([{"command": cmd, "time": str(time_ms), "progress": 0}])
    key = "pjCommand" if ch == "pj" else "sxCommand"
    res = await api_post(client, "sendCommand", {
        "command": {key: payload, "deviceId": dev_id},
        "account": ACCOUNT, "code": code
    })
    if res.get("code") == 0:
        return {"success": True, "device": cfg["name"], "deviceId": dev_id,
                "channel": ch, "channelLabel": c["label"], "action": action,
                "intensity": intensity if action != "stop" else 0, "duration": time_ms,
                "command": cmd, "message": f"{cfg['name']} {c['label']} 已{desc}"}
    return {"success": False, "error": res.get("message", "发送失败"), "detail": res}

server = MCPServer("cachito-universal-mcpiversal-mcp")

@server.tool(name="toy_control")
async def toy_control(code: str, action: str = "vibrate", channel: str = "吮吸",
                      intensity: int = 50, duration: int = 3000) -> str:
    async with httpx.AsyncClient() as client:
        dev_id, dev_name, err = await get_device_info(client, code)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)
        cfg, kw = match_config(dev_name)
        cfg = inject_id(cfg, dev_id)
        ch, err = resolve_ch(cfg, channel)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)
        err = await join(client, code)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)
        result = await send_cmd(client, code, dev_id, cfg, ch,
                                "stop" if action == "stop" else "vibrate", intensity, duration)
        return json.dumps(result, ensure_ascii=False, indent=2)

@server.tool(name="list_devices")
async def list_devices(code: str) -> str:
    async with httpx.AsyncClient() as client:
        dev_id, dev_name, err = await get_device_info(client, code)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)
        cfg, kw = match_config(dev_name)
        cfg = inject_id(cfg, dev_id)
        return json.dumps({
            "success": True, "deviceId": dev_id, "deviceName": dev_name,
            "matchedTemplate": kw,
            "channels": {k: {"name": v["label"], "code": k} for k, v in cfg["channels"].items()},
            "account": ACCOUNT
        }, ensure_ascii=False, indent=2)

@server.tool(name="discover_devices")
async def discover_devices() -> str:
    return json.dumps({
        "success": True,
        "note": "device_id 通过 getRemoteInfo 实时获取",
        "devices": [{"keyword": k, "channels": [{"code": c, "name": v["label"]} for c, v in t["channels"].items()]}
                    for k, t in DEVICE_TEMPLATES.items()],
        "channelAliases": CHANNEL_MAP
    }, ensure_ascii=False, indent=2)

# 关键修复：禁用 DNS 重绑定保护，避免 Render 421 错误
app = server.streamable_http_app(
    streamable_http_path="/mcp",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"Running at http://{host}:{port}/mcp")
    uvicorn.run(app, host=host, port=port, proxy_headers=True)
