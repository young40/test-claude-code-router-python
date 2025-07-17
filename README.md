# Claude Code Router

一个用于路由和管理 Claude API 请求的 Python 服务。

## 安装和使用

### 启动服务

```bash
# 启动服务
python3 cli.py start

# 查看服务状态
python3 cli.py status

# 停止服务
python3 cli.py stop

# 执行代码命令
python3 cli.py code "Write a Hello World"

# 查看版本
python3 cli.py -v
# 或者
python3 cli.py version

# 查看帮助
python3 cli.py -h
# 或者
python3 cli.py help
```

### 直接运行服务器

如果你想直接启动服务器（前台运行，可以看到日志）：

```bash
python3 index.py
```

## 配置

首次运行时，程序会提示你输入配置信息：

- Provider Name: 提供商名称
- Provider API KEY: API 密钥
- Provider URL: API 基础 URL
- MODEL Name: 模型名称

配置文件会保存在 `~/.claude-code-router/config.json`

## 服务信息

- 默认端口: 3456
- 默认主机: 127.0.0.1
- 配置目录: `~/.claude-code-router/`
- PID 文件: `~/.claude-code-router/.claude-code-router.pid`

## API 端点

服务启动后，你可以通过以下方式访问：

- GET `http://127.0.0.1:3456/` - 检查服务状态
- POST `http://127.0.0.1:3456/` - 发送请求

## 日志

服务运行时会在控制台输出日志信息，包括：
- 服务启动信息
- 请求处理日志
- 错误信息

按 `Ctrl+C` 可以停止服务。