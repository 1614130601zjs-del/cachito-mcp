# Cachito 全线产品万能 MCP

全系列设备自动识别，支持吮吸 / 入体 / 同时控制，MCP 协议接入。

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/1614130601zjs-del/cachito-mcp)

## 部署后使用

MCP 地址：`https://cachito-mcp.onrender.com/mcp`

## 工具说明

### toy_join
通过邀请码加入远程控制。

- `invite_code`：APP生成的6位邀请码（必填）

### toy_control
控制设备震动或停止，自动识别设备类型，调用者自行决定通道。

- `action`：`vibrate`（震动）或 `stop`（停止），必填
- `channel`：`sx`（吮吸端）、`pj`（入体端）、`both`（同时控制两端），默认 `sx`
- `intensity`：0-100，默认 30
- `duration`：持续时间（毫秒），默认 3000

### toy_state
查看当前连接状态。

## 环境变量

在 Render 中设置：
- `CACHITO_ACCOUNT`：你的 Cachito 账号 ID（必填）

## 一键部署

点击上面的按钮，登录 Render 后自动部署。部署后请在环境变量中填入你的账号 ID。
