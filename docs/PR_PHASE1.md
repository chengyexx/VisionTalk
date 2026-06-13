# Phase 1: 项目脚手架搭建

## 概述

搭建 Vision Talk — AI 视觉对话助手 的项目基础框架，确定技术栈和开发环境。

## 变更内容

### 前端 (React + Vite + TypeScript)
- 使用 `create-vite --template react-ts` 初始化项目
- Vite v8 构建系统，构建验证通过（20 模块，157ms）
- 结构：`src/App.tsx`, `src/main.tsx`, 标准 Vite 目录布局
- 已安装依赖：react, react-dom, typescript, vite, eslint

### 后端 (Python + FastAPI)
- FastAPI 应用骨架，含 WebSocket 端点
- 目录结构：`app/routes/`, `app/services/`, `app/config.py`
- 路由骨架：`/api/health` 健康检查, `/ws` WebSocket 连接点
- 已安装依赖：fastapi, uvicorn[standard], websockets
- 后端加载验证通过

### 项目配置
- `.gitignore`：Python + Node.js 标准忽略规则
- `README.md`：项目说明、架构图、快速开始指南、目录结构
- `backend/requirements.txt`：Python 依赖锁定

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React + TypeScript + Vite |
| 后端 | Python + FastAPI |
| 实时通信 | WebSocket |
| AI 管线 | LangGraph (后续) |
| 多模型网关 | LiteLLM (后续) |

## 验证

- ✅ 前端 `npm run build` 构建成功
- ✅ 后端 `python main.py` 加载成功
- ✅ Git 初始化，main 分支

## 下一步

Phase 2：边缘端预处理（Ring Buffer、帧差分关键帧检测、本地 VAD、WebRTC 采集）
