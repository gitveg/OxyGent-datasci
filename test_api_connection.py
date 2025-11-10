"""测试 API 连接的诊断脚本"""
import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(".env")


async def test_api_connection():
    """测试 LLM API 连接"""
    # 检查 .env 文件是否存在
    env_file = ".env"
    env_exists = os.path.exists(env_file)
    
    print("=" * 60)
    print("API 连接诊断工具")
    print("=" * 60)
    
    if env_exists:
        print(f"✓ 找到 .env 文件: {os.path.abspath(env_file)}")
    else:
        print(f"⚠️  未找到 .env 文件: {os.path.abspath(env_file)}")
        print("   当前工作目录:", os.getcwd())
    
    # 加载环境变量
    api_key = os.getenv("DEFAULT_LLM_API_KEY")
    base_url = os.getenv("DEFAULT_LLM_BASE_URL")
    model_name = os.getenv("DEFAULT_LLM_MODEL_NAME")
    
    print("\n环境变量检查：")
    print(f"  DEFAULT_LLM_API_KEY: {('已设置 (长度: ' + str(len(api_key)) + ')' if api_key else '❌ 未设置')}")
    print(f"  DEFAULT_LLM_BASE_URL: {base_url or '❌ 未设置'}")
    print(f"  DEFAULT_LLM_MODEL_NAME: {model_name or '❌ 未设置'}")

    # 检查环境变量
    if not api_key or not base_url or not model_name:
        print("\n" + "=" * 60)
        print("❌ 错误：缺少必要的环境变量")
        print("=" * 60)
        
        if not env_exists:
            print("\n💡 解决方案：")
            print("  1. 在项目根目录创建 .env 文件")
            print("  2. .env 文件格式（注意：不要使用引号）：")
            print("     DEFAULT_LLM_BASE_URL=https://api.chatanywhere.tech/v1")
            print("     DEFAULT_LLM_API_KEY=your_actual_api_key")
            print("     DEFAULT_LLM_MODEL_NAME=gpt-4o-mini")
        else:
            print("\n💡 .env 文件存在但环境变量未加载，可能的原因：")
            print("  1. .env 文件格式错误（值不应该有引号）")
            print("  2. .env 文件中有空行或格式问题")
            print("  3. API_KEY 为空字符串")
            print("\n正确的 .env 格式示例：")
            print("  DEFAULT_LLM_BASE_URL=https://api.chatanywhere.tech/v1")
            print("  DEFAULT_LLM_API_KEY=sk-xxxxxxxxxxxxx")
            print("  DEFAULT_LLM_MODEL_NAME=gpt-4o-mini")
            print("\n错误的格式（不要这样写）：")
            print('  DEFAULT_LLM_API_KEY=""  # ❌ 有引号且为空')
            print('  DEFAULT_LLM_API_KEY="sk-xxx"  # ❌ 不需要引号')
        
        return False
    
    # 检查 API Key 是否为空字符串
    if api_key.strip() == "":
        print("\n⚠️  警告：API_KEY 是空字符串，请填入实际的 API 密钥")
        return False

    print(f"✓ 环境变量检查通过")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model_name}")
    print(f"  API Key: {'*' * 20}...{api_key[-4:] if len(api_key) > 4 else ''}")

    # 构建请求 URL
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = f"{url}/chat/completions"

    print(f"\n请求 URL: {url}")

    # 构建请求
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Hello, this is a test message."}
        ],
        "max_tokens": 10,
    }

    print("\n正在测试 API 连接...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            print(f"\n响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("✓ API 连接成功！")
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"].get("content", "")
                    print(f"✓ 收到响应: {content[:50]}...")
                return True
            else:
                print(f"❌ API 请求失败")
                print(f"  状态码: {response.status_code}")
                print(f"  响应内容: {response.text[:500]}")
                
                # 常见错误诊断
                if response.status_code == 401:
                    print("\n💡 可能的原因：API 密钥无效或过期")
                elif response.status_code == 403:
                    print("\n💡 可能的原因：API 密钥权限不足")
                elif response.status_code == 429:
                    print("\n💡 可能的原因：请求频率过高，请稍后重试")
                elif response.status_code == 500:
                    print("\n💡 可能的原因：API 服务器内部错误")
                elif response.status_code == 567:
                    print("\n💡 可能的原因：")
                    print("  1. API 密钥无效或过期")
                    print("  2. 账户余额不足或配额用完")
                    print("  3. API 服务暂时不可用")
                    print("  4. 请求格式不正确")
                    print("\n建议：")
                    print("  - 检查 API 密钥是否正确")
                    print("  - 登录 API 服务商网站检查账户状态")
                    print("  - 查看 API 文档确认请求格式")
                
                return False

    except httpx.TimeoutException:
        print("❌ 请求超时")
        print("💡 可能的原因：网络连接问题或 API 服务器响应慢")
        return False
    except httpx.ConnectError:
        print("❌ 连接失败")
        print("💡 可能的原因：")
        print("  - Base URL 不正确")
        print("  - 网络连接问题")
        print("  - API 服务器不可用")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {type(e).__name__}: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_api_connection())
    sys.exit(0 if success else 1)

