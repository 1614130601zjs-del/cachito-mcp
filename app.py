#!/usr/bin/env python3
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

CHANNEL_MAP = {
    "吮吸": "sx", "吸": "sx", "口吸": "sx", "秒潮": "sx", "舔": "sx",
    "入体": "pj", "脉冲": "pj", "炮机": "pj", "抽插": "pj",
    "震动": "pj", "振": "pj", "伸缩": "pj",
}

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

current_code = None
current_device_id = None
current_device_name = None
current_config = None

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
    return dev_id, dev_name, None

def match_config(name):
    up = (name or "").upper()
    for kw, tmpl in DEVICE_TEMPLATES.items():
        if kw.upper() in up:
            cfg = copy.deepcopy(tmpl)
            cfg["name"] = name
            return cfg, kw
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
        return None, "不支持" + user_ch + "，可用: " + avail
    for code, info in channels.items-0000000000",
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

current_code = None
current_device_id = None
current_device_name = None
current_config = None

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
    return dev_id, dev_name, None

def match_config(name):
    up = (name or "").upper()
    for kw, tmpl in DEVICE_TEMPLATES.items():
        if kw.upper() in up:
            cfg = copy.deepcopy(tmpl)
            cfg["name"] = name
            return cfg, kw
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
        return None, "不支持" + user_ch + "，可用: " + avail
    for code, info in channels.items():
        if ch in info["label"].lower() or info["label"].lower() in ch:
            return code, None
    avail = ", ".join(k + "(" + v["label"] + ")" for k, v in channels.items())
    return None, "无法识别" + user_ch + "，可用: " + avail

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

async def do_join(invite_code):
    global current_code, current_device_id, current_device_name, current_config
    dev_id, dev_name, err = await get_device_info(invite_code)
    if err:
        return "fail: " + err
    err = await join_remote(invite_code)
    if err:
        return "fail: " + err
    cfg, kw = match_config(dev_name)
    cfg = inject_id(cfg, dev_id)
    current_code = invite_code
    current_device_id = dev_id
    current_device_name = dev_name
    current_config = cfg
    return "ok"

async def do_control(action, channel, intensity, duration):
    global current_code, current_device_id, current_config
    if not current_code:
        return "fail: 请先调用 toy_join 设置邀请码"
    if not current_config:
        return "fail: 设备未初始化"
    ch, err = resolve_channel(current_config, channel)
    if err:
        return "fail: " + err
    return await send_command(
        current_code, current_device_id, current_config, ch,
        "stop" if action == "stop" else "vibrate",
        intensity, duration
    )

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

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "cachito-mcp", "version": "3.1"},
                "capabilities": {"tools": {}}
            }
        })

    if method == "notifications/initialized":
        return JSONResponse({}, status_code=202)

    if method == "tools/list":
        tools = [
            {
                "name": "toy_join",
                "description": "输入邀请码加入远程控制",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "invite_code": {"type": "string", "description": "APP生成的6位邀请码"}
                    },
                    "required": ["invite_code"]
                }
            },
            {
                "name": "toy_control",
                "description": "控制设备启动或停止，支持中文指令：吮吸、入体、脉冲等",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["vibrate", "stop"], "default": "vibrate", "description": "vibrate启动，stop停止"},
                        "channel": {"type": "string", "default": "吮吸", "description": "功能通道"},
                        "intensity": {"type": "integer", "default": 50, "description": "强度0-100"},
                        "duration": {"type": "integer", "default": 3000, "description": "持续时间(ms)"}
                    }
                }
            }
        ]
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools}
        })

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})
        if name == "toy_join":
            result_text = await do_join(args.get("invite_code", ""))
        elif name == "toy_control":
            result_text = await do_control(
                args.get("action", "vibrate"),
                args.get("channel", "吮吸"),
                args.get("intensity", 50),
                args.get("duration", 3000)
            )
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Unknown tool: " + name}
            })
        return JSONResponse({
            "jsonrpc": "2.0",
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
    uvicorn.run(app, host=host, port=port, workers=1)  # 关键：强制单 worker
