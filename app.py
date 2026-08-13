from flask import Flask, request, jsonify
import json
import httpx
import os
import asyncio

app = Flask(__name__)

ACCOUNT = os.environ.get("CACHITO_ACCOUNT", "52575934")

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
}

async def get_device_id(code):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.youtao.top/api/appRemote/getRemoteInfo",
            json={"account": ACCOUNT, "code": code}
        )
        data = r.json()
        if data.get("code") != 0:
            return None, data.get("message")
        return data.get("data", {}).get("remote", {}).get("deviceId"), None

async def send_toy_command(code, action="vibrate", channel="sx", intensity=50, duration=3000, pulse_type=None):
    async with httpx.AsyncClient() as client:
        device_id, err = await get_device_id(code)
        if err:
            return {"error": f"获取设备信息失败: {err}"}
        if device_id not in DEVICE_CONFIG:
            return {"error": f"不支持的设备ID: {device_id}"}
        
        config = DEVICE_CONFIG[device_id]
        if channel not in config["channels"]:
            return {"error": f"设备 {config['name']} 不支持 '{channel}' 通道"}
        
        channel_config = config["channels"][channel]
        
        join = await client.post(
            "https://www.youtao.top/api/appRemote/joinRemote",
            json={"account": ACCOUNT, "code": code}
        )
        if join.json().get("code") != 0:
            return {"error": "加入远程失败", "detail": join.json()}
        
        if action == "stop":
            cmd = channel_config["stop"]
            time_ms = 500
        else:
            hex_val = format(channel_config["formula"](intensity), '02x')
            cmd = channel_config["template"].replace("{hex}", hex_val)
            if "{pulse}" in cmd and pulse_type is not None:
                cmd = cmd.replace("{pulse}", str(pulse_type))
            time_ms = duration
        
        payload = json.dumps([{"command": cmd, "time": str(time_ms), "progress": 0}])
        cmd_key = "pjCommand" if channel == "pj" else "sxCommand"
        send = await client.post(
            "https://www.youtao.top/api/appRemote/sendCommand",
            json={
                "command": {cmd_key: payload, "deviceId": device_id},
                "account": ACCOUNT,
                "code": code
            }
        )
        result = send.json()
        if result.get("code") == 0:
            result["device"] = config["name"]
            result["deviceId"] = device_id
            result["channel"] = channel
        return result

# ===== 核心修改：根路径 POST =====
@app.route('/', methods=['POST'])
def mcp_handler():
    data = request.get_json()
    if not data:
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}), 400

    req_id = data.get("id")
    method = data.get("method")

    if method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [{
                    "name": "toy_control",
                    "description": "全系列万能遥控器",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "6位邀请码"},
                            "action": {"type": "string", "enum": ["vibrate", "stop"], "default": "vibrate"},
                            "channel": {"type": "string", "enum": ["sx", "pj"], "default": "sx"},
                            "intensity": {"type": "integer", "minimum": 0, "maximum": 100, "default": 50},
                            "duration": {"type": "integer", "default": 3000}
                        },
                        "required": ["code"]
                    }
                }]
            }
        })

    if method == "tools/call":
        params = data.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})

        if name != "toy_control":
            return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}), 404

        code = args.get("code")
        if not code:
            return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "缺少 'code'"}}), 400

        try:
            result = asyncio.run(send_toy_command(
                code,
                args.get("action", "vibrate"),
                args.get("channel", "sx"),
                args.get("intensity", 50),
                args.get("duration", 3000),
                args.get("pulse_type")
            ))
            return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as e:
            return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}), 500

    return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}), 404

@app.route('/')
def index():
    return "Cachito Universal MCP OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
