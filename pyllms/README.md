# PyLLMs

PyLLMs 是一个 Python 实现的 LLM 服务，用于统一管理和转换不同 LLM 提供商的 API。

## 功能特点

- 支持多种 LLM 提供商（如 OpenAI、Anthropic 等）
- 统一的请求和响应格式
- 可扩展的转换器系统
- 支持流式响应
- 支持工具调用

## 安装

```bash
# 安装依赖
pip install fastapi uvicorn httpx python-dotenv

# 克隆仓库
git clone https://github.com/yourusername/pyllms.git
cd pyllms
```

## 使用方法

### 启动服务

```bash
python main.py --port 3000 --host 127.0.0.1 --log
```

### 命令行参数

- `--config`: 配置文件路径 (默认: ./config.json)
- `--port`: 服务端口 (默认: 3000)
- `--host`: 服务主机地址 (默认: 127.0.0.1)
- `--log`: 启用日志记录
- `--log-file`: 日志文件路径 (默认: pyllms.log)

### 配置文件示例

```json
{
  "providers": [
    {
      "name": "openai",
      "api_base_url": "https://api.openai.com/v1/chat/completions",
      "api_key": "your-api-key",
      "models": ["gpt-3.5-turbo", "gpt-4"]
    },
    {
      "name": "anthropic",
      "api_base_url": "https://api.anthropic.com/v1/messages",
      "api_key": "your-api-key",
      "models": ["claude-2", "claude-instant-1"]
    }
  ]
}
```

## API 端点

### 聊天完成

- OpenAI 兼容端点: `/v1/chat/completions`
- Anthropic 兼容端点: `/v1/messages`

### 提供商管理

- 获取所有提供商: `GET /providers`
- 获取特定提供商: `GET /providers/{id}`
- 创建提供商: `POST /providers`
- 更新提供商: `PUT /providers/{id}`
- 删除提供商: `DELETE /providers/{id}`
- 切换提供商状态: `PATCH /providers/{id}/toggle`

## 扩展

### 添加新的转换器

1. 在 `src/transformer` 目录下创建新的转换器文件
2. 实现 `Transformer` 接口
3. 在 `src/transformer/__init__.py` 中注册新的转换器

## 许可证

MIT