#!/usr/bin/env python3
"""
Cachito 全线产品万能 MCP - 纯 POST /mcp 接入版
参考 kitten-paw-control 结构，无 SSE，无 SDK，手写 JSON-RPC
"""
import json
import os
import logging
import copy
import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cachito-mcp")

ACCOUNT = os.environ.get("CACHITO_ACCOUNT", "52575934")
API_BASE = "https://www.youtao.top/api/appRemote"

# 中文指令 -> 通道代码
CHANNEL_MAP = {
    "吮吸": "sx", "吸": "sx", "口吸": "sx", "秒潮": "sx", "舔": "sx",
    "入体": "pj", "脉冲": "pj", "炮机": "pj", "抽插": "pj",
    "震动": "pj", "振": "pj", "伸缩": "pj",
}

# 设备模板库（以名称为 key，device_id 从 API 实时获取后注入）
# 模板占位符: {id_hex2}, {id_hex4}, {intensity_hex}
DEVICE_TEMPLATES = {
    "猫爪": {
        "channels": {
            "sx": {
                "template": "710001{id_hex2}-0400-{id_hex4}-0302-{intensity_hex}00000000",
                "stop": "710001{id_hex2}-0400-{id_hex4}-0601-0200000000",
                "formula": lambda i: round(i * 0.75 + 25),
                "label": "吮吸"
            }
        }
    },
    "失控": {
        "channels": {
            "sx": {
                "template": "710002{id_hex2}-0400-{id_hex4}-0302-{intensity_hex}00000000",
                "stop": "710002{id_hex2}-0400-{id_hex4}-0302-0000000000",
                "formula": lambda i: round(i * 0.75 + 25),
                "label": "吮吸"
            },
            "pj": {
                "template": "710002{id_hex2}-0400-{id_hex4}-050A-{intensity_hex}00000000",
                "stop": "710002{id_hex2}-0400-{id_hex4}-0601-0000000000",
                "formula": lambda i: round(i * 0.75 + 25),
                "label": "脉冲/入体"
            }
        }
    },
    "偷欢": {
        "channels": {
            "sx": {
                "template": "71000C{id_hex2}-8200-{id_hex4}-0100-{intensity_hex}000002",
                "stop": "71000C{id_hex2}-0F00-{id_hex4}-0100-0000000000",
                "formula": lambda i: round(i * 0.5 + 50),
                "label": "吮吸"
            }
        }
    },
    "漫步": {
        "channels": {
            "sx": {
                "template": "710017{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
                "stop": "710017{id_hex2}-0100-{id_hex4}-0100-6400000002",
                "formula": lambda i: round(i * 0.5 + 50),
                "label": "吮吸"
            }
        }
    },
    "SK": {
        "channels": {
            "sx": {
                "template": "710017{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
                "stop": "710017{id_hex2}-0100-{id_hex4}-0100-6400000002",
                "formula": lambda i: round(i * 0.5 + 50),
                "label": "吮吸"
            }
        }
    },
}

# 通用回退模板
GENERIC = {
    "channels": {
        "sx": {
            "template": "7100{id_hex2}-5100-{id_hex4}-0100-{intensity_hex}000002",
            "stop": "7100{id_hex2}-0100-{id_hex4}-0100-6400000002",
            "formula": lambda i: round(i * 0.5 + 50),
            "label": "吮吸（通用）"
        }
    }
}

# 全局状态
current_code = None


async def api_post(endpoint, payload):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(API_BASE + "/" + endpoint, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error("API [%s] %s", endpoint, e)
        return {"code": -1, "message": str(e)}


async def get_device_info(code):
    data = await api_post("getRemoteInfo", {"account": ACCOUNT, "code": code})
    if data.get("code") != 0:
        return None, None, data.get("message", "获取失败")
    remote = data.get("data", {}).get("remote", {})
    dev_id = remote.get("deviceId")
    dev_name = remote.get("deviceName", "未知")
    if dev_id is None:
        return None, None, "无设备ID"
    logger.info("getRemoteInfo: %s (ID=%s)", dev_name, dev_id)
    return dev_id, dev_name, None


def match_config(name):
    up = (name or "").upper()
    for kw, tmpl in DEVICE_TEMPLATES.items():
        if kw.upper() in up:
            cfg = copy.deepcopy(tmpl)
            cfg["name"] = name
            return cfg, kw
    logger.warning("未匹配: %s，使用通用模板", name)
    cfg = copy.deepcopy(GENERIC)
    cfg["name"] = name
    return cfg, "通用"


def inject_id(cfg, dev_id):
    h2 = format(dev_id, "02x")
    h4 = format(dev_id, "04x")
    for ch in cfg.get("channels", {}).values():
        for k in ("template", "stop"):
            if k in ch:
                ch[k] = ch[k].replace("{id_hex2}", h2).replace("{id_hex4}", h4)
    return cfg


def resolve_channel(cfg, user_ch):
    ch = user_ch.strip().lower()
    channels = cfg.get("channels", {})
    if ch in channels:
        return ch, None
    if ch in CHANNEL_MAP:
        m = CHANNEL_MAP[ch]
        if m in channels:
            return m, None
        avail = ", ".join(k + "(" + v["label"] + ")" for k, v in channels.items())
        return None, "不支持'" + user_ch + "'，可用: " + avail
    for code, info in channels.items():
        if ch in info["label"].lower() or info["label"].lower() in ch:
            return code, None
    avail = ", ".join(k + "(" + v["label"] + ")" for k, v in channels.items())
    return None, "无法识别'" + user_ch + "'，可用: " + avail


async def join_remote(code):
    data = await api_post("joinRemote", {"account": ACCOUNT, "code": code})
    if data.get("code") != 0:
        return data.get("message", "加入失败")
    return None


async def send_command(code, dev_id, cfg, ch, action, intensity, duration):
    c = cfg["channels"][ch]
    if action == "stop":
        cmd = c["stop"]
        time_ms = 500
    else:
        v = max(0, min(100, intensity))
        cmd = c["template"].replace("{intensity_hex}", format(c["formula"](v), "02x"))
        time_ms = max(500, duration)
    payload = json.dumps([{"command": cmd, "time": str(time_ms), "progress": 0}])
    key = "pjCommand" if ch == "pj" else "sxCommand"
    res = await api_post("sendCommand", {
        "command": {key: payload, "deviceId": dev_id},
        "account": ACCOUNT,
        "code": code
    })
    if res.get("code") == 0:
        return "ok"
    return "fail: " + res.get("message", "发送失败")


async def do_toy_control(code, action, channel, intensity, duration):
    global current_code
    current_code = code

    dev_id, dev_name, err = await get_device_info(code)
    if err:
        return "fail: " + err

    cfg, kw = match_config(dev_name)
    cfg = inject_id(cfg, dev_id)

    ch, err = resolve_channel(cfg, channel)
    if err:
        return "fail: " + err

    err = await join_remote(code)
    if err:
        return "fail: " + err

    return await send_command(
        code, dev_id, cfg, ch,
        "stop" if action == "stop" else "vibrate",
        intensity, duration
    )


async def do_list_devices(code):
    dev_id, dev_name, err = await get_device_info(code)
    if err:
        return "fail: " + err
    cfg, kw = match_config(dev_name)
    cfg = inject_id(cfg, dev_id)
    parts = [v["label"] + "(" + k + ")" for k, v in cfg["channels"].items()]
    return dev_name + " | " + ", ".join(parts)


async def do_discover_devices():
    lines = []
    for kw, t in DEVICE_TEMPLATES.items():
        chs = ", ".join(v["label"] for v in t["channels"].values())
        lines.append(kw + ": " + chs)
    return "; ".join(lines)


# ========== JSON-RPC 处理 ==========

async def handle_rpc(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400
        )

    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id")
    logger.info("RPC: %s", method)

    # 1. initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "cachito-universal-mcp", "version": "2.0"},
                "capabilities": {"tools": {}}
            }
        })

    # 2. notifications/initialized
    if method == "notifications/initialized":
        return JSONResponse({}, status_code=202)

    # 3. tools/list
    if method == "tools/list":
        tools = [
            {
                "name": "toy_control",
                "description": "控制设备，支持中文指令：吮吸、入体、脉冲等",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "邀请码"},
                        "action": {"type": "string", "enum": ["vibrate", "stop"], "default": "vibrate"},
                        "channel": {"type": "string", "default": "吮吸"},
                        "intensity": {"type": "integer", "default": 50},
                        "duration": {"type": "integer", "default": 3000}
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "list_devices",
                "description": "查询设备信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"]
                }
            },
            {
                "name": "discover_devices",
                "description": "获取支持的设备清单",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools}
        })

    # 4. tools/call
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})

        if name == "toy_control":
            result_text = await do_toy_control(
                args.get("code", ""),
                args.get("action", "vibrate"),
                args.get("channel", "吮吸"),
                args.get("intensity", 50),
                args.get("duration", 3000)
            )
        elif name == "list_devices":
            result_text = await do_list_devices(args.get("code", ""))
        elif name == "discover_devices":
            result_text = await do_discover_devices()
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Unknown tool: " + name}
            })

        return JSONResponse({
            "jsonrpc": "2.0",
.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
                "isError": result_text.startswith("fail:")
            }
        })

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "Method not found: " + str(method)}
    })


async def handle_mcp_get(request: Request):
    return JSONResponse({
        "status": "MCP server running",
        "endpoint": "/mcp",
        "method": "POST only (JSON-RPC)",
        "protocolVersion": "2024-11-05"
    })


middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
]

app = Starlette(
    middleware=middleware,
    routes=[
        Route("/mcp", handle_rpc, methods=["POST"]),
        Route("/mcp", handle_mcp_get, methods=["GET"]),
        Route("/", lambda r: JSONResponse({"status": "ok", "mcp_endpoint": "/mcp"}), methods=["GET"])
    ]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info("Running at http://%s:%s/mcp", host, port)
    uvicorn.run(app, host=host, port=port)
