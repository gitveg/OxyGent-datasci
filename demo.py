import asyncio
import os
import sys

from dotenv import load_dotenv
from oxygent import MAS, Config, oxy, preset_tools

# 加载 .env 文件
load_dotenv(".env")

Config.set_agent_llm_model("default_llm")

# 检查环境变量
api_key = os.getenv("DEFAULT_LLM_API_KEY")
base_url = os.getenv("DEFAULT_LLM_BASE_URL")
model_name = os.getenv("DEFAULT_LLM_MODEL_NAME")

# if not api_key or not base_url or not model_name:
#     print("=" * 60)
#     print("错误：缺少必要的环境变量！")
#     print("=" * 60)
#     print("请设置以下环境变量：")
#     print("  - DEFAULT_LLM_API_KEY: API 密钥")
#     print("  - DEFAULT_LLM_BASE_URL: API 基础 URL")
#     print("  - DEFAULT_LLM_MODEL_NAME: 模型名称")
#     print("\n当前值：")
#     print(f"  DEFAULT_LLM_API_KEY: {'已设置' if api_key else '未设置'}")
#     print(f"  DEFAULT_LLM_BASE_URL: {base_url or '未设置'}")
#     print(f"  DEFAULT_LLM_MODEL_NAME: {model_name or '未设置'}")
#     print("\n设置方法（Windows PowerShell）：")
#     print('  $env:DEFAULT_LLM_API_KEY="your_api_key"')
#     print('  $env:DEFAULT_LLM_BASE_URL="https://api.chatanywhere.tech/v1"')
#     print('  $env:DEFAULT_LLM_MODEL_NAME="gpt-3.5-turbo"')
#     print("\n或者创建 .env 文件：")
#     print("  DEFAULT_LLM_API_KEY=your_api_key")
#     print("  DEFAULT_LLM_BASE_URL=https://api.chatanywhere.tech/v1")
#     print("  DEFAULT_LLM_MODEL_NAME=gpt-3.5-turbo")
#     print("=" * 60)
#     sys.exit(1)

# print(f"✓ 环境变量检查通过")
# print(f"  API URL: {base_url}")
# print(f"  模型: {model_name}")
# print(f"  API Key: {'*' * 20}...{api_key[-4:] if len(api_key) > 4 else ''}")

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
    ),
    preset_tools.time_tools,
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool that can query the time",
        tools=["time_tools"],
    ),
    preset_tools.file_tools,
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool that can operate the file system",
        tools=["file_tools"],
    ),
    preset_tools.math_tools,
    oxy.ReActAgent(
        name="math_agent",
        desc="A tool that can perform mathematical calculations.",
        tools=["math_tools"],
    ),
    oxy.ReActAgent(
        is_master=True,
        name="master_agent",
        sub_agents=["time_agent", "file_agent", "math_agent"],
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="What time is it now? Please save it into time.txt."
        )


if __name__ == "__main__":
    asyncio.run(main())
