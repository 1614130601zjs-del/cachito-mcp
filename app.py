"""
Cachito 万能遥控器 MCP 服务
支持全系列设备自动识别，调用者自行选择通道（sx / pj / both）
JSON-RPC over HTTP POST，兼容标准 MCP 客户端
"""
import json
import os
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

ACCOUNT = os.environ.get("CACHITO_ACCOUNT", "你的账号ID")
code = None

# ============================================================
# 全系列设备指令配置（从官方 APP 反编译提取）
# ============================================================
DEVICE_CONFIG = {
    13: {
        "name": "小猫爪",
        "channels": {
            "sx": {
                "template": "710001**-0400-####-0302-{hex}00000000",
                "stop": "710001**-0400-####-0601-0200000000",
                "formula": lambda i: round(i * 0.75 + 25)
            }
        }
    },
    15: {
        "name": "设备15",
        "channels": {
            "sx": {
                "template": "710004**-0400-####-0302-{hex}00000000",
                "stop": "710004**-0400-####-0302-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            }
        }
    },
    22: {
        "name": "失控2.0",
        "channels": {
            "sx": {
                "template": "710002**-0400-####-0302-{hex}00000000",
                "stop": "710002**-0400-####-0302-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            },
            "pj": {
                "template": "710002**-0400-####-050A-{hex}00000000",
                "stop": "710002**-0400-####-0601-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            }
        }
    },
    23: {
        "name": "设备23",
        "channels": {
            "sx": {
                "template": "710004**-0400-####-0302-{hex}00000000",
                "stop": "710004**-0400-####-0302-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            },
            "pj": {
                "template": "710000**-0400-####-050A-{hex}00000000",
                "stop": "710000**-0400-####-0601-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            }
        }
    },
    24: {
        "name": "设备24",
        "channels": {
            "sx": {
                "template": "710000**-0400-####-0302-{hex}00000000",
                "stop": "710000**-0400-####-0302-0000000000",
                "formula": lambda i: i  # 直接使用强度值
            },
            "pj": {
                "template": "710000**-0400-####-050A-{hex}00000000",
                "stop": "710000**-0400-####-0601-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            }
        }
    },
    25: {
        "name": "设备25",
        "channels": {
            "sx": {
                "template": "710005**-0400-####-0302-{hex}00000000",
                "stop": "710005**-0400-####-0302-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            }
        }
    },
    26: {
        "name": "设备26",
        "channels": {
            "sx": {
                "template": "710006**-0400-####-0302-{hex}00000000",
                "stop": "710006**-0400-####-0302-0000000000",
                "formula": lambda i: round(i * 0.75 + 25)
            }
        }
    },
    32: {
        "name": "设备32",
        "channels": {
            "sx": {
                "template": "710009**-8200-####-0100-{hex}000002",
                "stop": "710009**-0F00-####-0100-3211643202",
                "formula": lambda i: round(i * 0.5 + 50)
            }
        }
    },
    33: {
        "name": "设备33",
        "channels": {
            "sx": {
                "template": "71000A**-8200-####-0100-{hex}000002",
                "stop": "71000A**-0F00-####-0100-0000000000",
                "formula": lambda i: round(i * 0.5 + 50)
            }
        }
    },
    34: {
        "name": "设备34",
        "channels": {
            "sx": {
                "template": "710007**-8200-####-0100-{hex}000002",
                "stop": "710007**-0200-####-0100-6400000002",
                "formula": lambda i: round(i * 0.5 + 50)
            },
            "pj": {
                "template": "710007**-8100-####-0100-0A{hex}1c0002",
                "stop": "710007**-0100-####-0100-6400000002",
                "formula": lambda i: round(60 - i * 0.57)
            }
        }
    },
    36: {
        "name": "偷欢pro",
        "channels": {
            "sx": {
                "template": "71000C**-8200-####-0100-{hex}000002",
                "stop": "71000C**-0F00-####-0100-0000000000",
                "formula": lambda i: round(i * 0.5 + 50)
            }
        }
    },
    38: {
        "name": "SK4",
        "channels": {
            "sx": {
                "template": "710017**-5100-####-0100-{hex}000002",
                "stop": "710017**-0100-####-0100-6400000002",
                "formula": lambda i: round(i * 0.5 + 50)
            }
        }
    },
    41: {
        "name": "设备41",
        "channels": {
            "sx": {
                "template": "71000B**-8200-####-0100-{hex}000002",
                "stop": "71000B**-0200-####-0100-6400000002",
                "formula": lambda i: round(i * 0.5 + 50)
            },
            "pj": {
                "template": "71000B**-8100-####-0100-0A{hex}1c0002",
                "stop": "71000B**-0100-####-0100-6400000002",
                "formula": lambda i: round(60 - i * 0.57)
            }
        }
    },
    42: {
        "name": "设备42",
        "channels": {
            "sx": {
                "template": "71001A**-8200-####-0100-{hex}000002",
                "stop": "71001A**-0200-####-0100-3211643202",
                "formula": lambda i: round(i * 0.5 + 50)
            }
        }
    },
}

# ============================================================
# 核心业务逻辑
# ============================================================

async def get_device_id(invite_code: str):
    """通过邀请码获取设备ID"""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.youtao.top/api/appRemote/getRemoteInfo",
            json={"account": ACCOUNT, "code": invite_code}
        )
        data = r.json()
        if data.get("code") != 0:
            return None, data.get("message")
        return data.get("data", {}).get("remote", {}).get("deviceId"), None

async def toy_join(invite_code: str) -> str:
    """加入远程控制"""
    global code
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.youtao.top/api/appRemote/joinRemote",
            json={"account": ACCOUNT, "code": invite_code}
        )
        result = r.json()
        if result.get("code") == 0:
            code = invite_code
            return "加入成功！邀请码已就绪。"
        return f"加入失败: {result.get('message')}。请重新生成邀请码。"

async def _send_single_channel(action: str, channel: str, intensity: int, duration: int) -> str:
    """发送单个通道的指令（内部函数）"""
    global code
    device_id, err = await get_device_id(code)
    if err:
        return f"获取设备信息失败: {err}"
    if device_id not in DEVICE_CONFIG:
        return f"不支持的设备ID: {device_id}"

    config = DEVICE_CONFIG[device_id]
    if channel not in config["channels"]:
        return f"设备 {config['name']} 不支持 '{channel}' 通道"

    channel_config = config["channels"][channel]

    if action == "stop":
        cmd = channel_config["stop"]
        time_ms = 500
        label = f"{config['name']} {channel}端 已停止"
    else:
        hex_val = format(channel_config["formula"](intensity), '02x')
        cmd = channel_config["template"].replace("{hex}", hex_val)
        time_ms = duration
        # 使用双引号避免转义问题
        label = f"{config['name']} {channel}端 强度{intensity}%，持续{duration/1000}秒"

    payload = json.dumps([{"command": cmd, "time": str(time_ms), "progress": 0}])
    cmd_key = "pjCommand" if channel == "pj" else "sxCommand"

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.youtao.top/api/appRemote/sendCommand",
            json={
                "command": {cmd_key: payload, "deviceId": device_id},
                "account": ACCOUNT,
                "code": code
            }
        )
        result = r.json()
        if result.get("code") == 0:
            return label + " ✓"
        return f"指令失败: {result.get('message')}"

async def toy_control(action: str, channel: str = "sx", intensity: int = 30, duration: int = 3000) -> str:
    """通用控制函数，调用者通过 channel 参数自行决定控制哪个通道"""
    global code
    if not code:
        return "还没加入远程。先让用户在APP生成邀请码，然后调用toy_join。"

    if channel == "both":
        sx_result = await _send_single_channel(action, "sx", intensity, duration)
        pj_result = await _send_single_channel(action, "pj", intensity, duration)
        return f"{sx_result}\n{pj_result}"

    return await _send_single_channel(action, channel, intensity, duration)

async def toy_state() -> str:
    return f"邀请码: {code or '未设置'}"

# ============================================================
# MCP JSON-RPC 处理器
# ============================================================

async def handle_rpc(request: Request):
    raw = await request.body()
    try:
        body = json.loads(raw)
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400
        )

    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id")

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "Cachito Universal MCP", "version": "1.0"},
                "capabilities": {"tools": {}}
            }
        })

    if method == "notifications/initialized":
        return JSONResponse({}, status_code=202)

    if method == "tools/list":
        tools = [
            {
                "name": "toy_join",
                "description": "通过邀请码加入远程控制",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "invite_code": {"type": "string", "description": "APP生成的邀请码"}
                    },
                    "required": ["invite_code"]
                }
            },
            {
                "name": "toy_control",
                "description": "控制设备震动或停止（自动识别设备类型，调用者自行决定通道）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["vibrate", "stop"], "description": "vibrate=震动, stop=停止"},
                        "channel": {"type": "string", "enum": ["sx", "pj", "both"], "default": "sx", "description": "sx=吮吸端, pj=入体端, both=同时控制两端"},
                        "intensity": {"type": "integer", "default": 30, "description": "强度 0-100"},
                        "duration": {"type": "integer", "default": 3000, "description": "持续时间(ms)"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "toy_state",
                "description": "查看当前连接状态",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools}
        })

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "toy_join":
            invite_code = arguments.get("invite_code", "")
            result_text = await toy_join(invite_code)
        elif tool_name == "toy_control":
            action = arguments.get("action", "")
            channel = arguments.get("channel", "sx")
            intensity = arguments.get("intensity", 30)
            duration = arguments.get("duration", 3000)
            result_text = await toy_control(action, channel, intensity, duration)
        elif tool_name == "toy_state":
            result_text = await toy_state()
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"}
            })

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
                "isError": False
            }
        })

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    })

async def handle_mcp_get(request: Request):
    return JSONResponse({
        "status": "MCP server running",
        "endpoint": "/mcp",
        "method": "POST only (JSON-RPC)",
        "protocolVersion": "2024-11-05"
    })

# ============================================================
# 启动配置
# ============================================================

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
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
