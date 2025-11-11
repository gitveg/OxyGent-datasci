import argparse
import asyncio
import json
import base64
import os, sys
from pathlib import Path

from dotenv import load_dotenv
from typing import Dict, List

# 导入提示词配置
from prompts_config import get_agent_prompt, MASTER_AGENT_PROMPT, MULTIMODAL_AGENT_PROMPT, TIME_AGENT_PROMPT, FILE_AGENT_PROMPT, MATH_AGENT_PROMPT, BROWSER_AGENT_PROMPT

# OxyGent 入口
from oxygent import MAS, Config, oxy, preset_tools, OxyRequest

DEFAULT_QUERY = "https://item.jd.com/100086113628.html 中的商品的商品编号是多少？"

script_path = Path(__file__).parent

# -----------------------------
# 配置与环境
# -----------------------------
def setup_env() -> None:
	"""
	加载 .env 与默认配置，设置日志与服务端口等基础配置。
	贡献者如需增加自定义配置，请在此函数中集中管理。
	"""
	load_dotenv(".env")
    # .env 参考文件内容：
    # DEFAULT_LLM_BASE_URL=""
    # DEFAULT_LLM_API_KEY=""
    # DEFAULT_LLM_MODEL_NAME="
	pass

# 将文件转为 Base64 编码
def file_to_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def save_results(results: List[Dict], output_path: str):
    """保存结果到 JSONL 文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"✓ 结果已保存到: {output_path}")

async def check_tool_permisssion(mas, oxy_space):
	"""检查是否有工具权限"""
	if "browser_agent" in mas.oxy_name_to_oxy:
		browser_agent = mas.oxy_name_to_oxy["browser_agent"]
		# 确保 run_python_code 在权限列表中
		if "run_python_code" not in browser_agent.permitted_tool_name_list:
			browser_agent.add_permitted_tool("run_python_code")
			print("✓ 已手动添加 run_python_code 权限到 browser_agent")


def build_oxy_space() -> list:
	"""
	构建核心 Oxy 空间：
	- 一个可通过环境变量配置的通用 HTTP LLM
	- 常用预设工具（time/file/math）
	- 基于 ReAct 范式的从属智能体 + 一个主智能体

	后续五个任务可在此追加自定义工具/智能体并挂到主智能体或作为并列入口。
	"""
	api_key = os.getenv("DEFAULT_LLM_API_KEY", "")
	base_url = os.getenv("DEFAULT_LLM_BASE_URL", "")
	model_name = os.getenv("DEFAULT_LLM_MODEL_NAME", "gpt-4o-mini")

	if not api_key or not base_url or not model_name:
		print("错误：请设置环境变量 DEFAULT_LLM_API_KEY, DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL_NAME")
		sys.exit(1)

	llm = oxy.HttpLLM(
		name="default_llm",
		api_key=api_key,
		base_url=base_url,
		model_name=model_name,
	)

	time_agent = oxy.ReActAgent(
		name="time_agent",
		desc="查询时间、日期与时间处理相关能力",
		tools=["time_tools"],
		prompt=TIME_AGENT_PROMPT,
	)
	file_agent = oxy.ReActAgent(
		name="file_agent",
		desc="进行本地文件系统读写与管理",
		tools=["file_tools"],
		prompt=FILE_AGENT_PROMPT,
	)
	math_agent = oxy.ReActAgent(
		name="math_agent",
		desc="执行数学计算、表达式求值、表格类数据计算",
		tools=["math_tools"],
		prompt=MATH_AGENT_PROMPT,
	)

	# 主智能体
	master_agent = oxy.ReActAgent(
		is_master=True,
		name="master_agent",
		desc="多工具编排与子智能体调度的总控智能体",
		# 授权：将 multimodal_agent 添加到主智能体的可调度列表
		sub_agents=["time_agent", "file_agent", "math_agent"],
		prompt=MASTER_AGENT_PROMPT,
	)

	# 预设工具实例
	tools = [
		preset_tools.time_tools,
		preset_tools.file_tools,
		preset_tools.math_tools,
		preset_tools.multimodal_tools,
		preset_tools.python_tools,
		preset_tools.string_tools,
	]

	# 后续五个任务的扩展挂点（示例占位，贡献者可在此处追加）
	# 示例：
	# advanced_retrieval_agent = oxy.ReActAgent(
	# 	name="advanced_retrieval_agent",
	# 	desc="复杂检索与网页浏览工具编排",
	# 	tools=["browser_tools", "retrieve_tools"],
	# )
	# master_agent.sub_agents.append("advanced_retrieval_agent")
		# 多模态智能体
	multimodal_agent = oxy.ReActAgent(
		name="multimodal_agent",
		desc="读取PDF和图片中的文本内容",
		tools=["multimodal_tools"],
		prompt=MULTIMODAL_AGENT_PROMPT,
	)
	master_agent.sub_agents.append("multimodal_agent")

	browser_server_dir = script_path / "mcp_servers"
	browser_tools = oxy.StdioMCPClient(
                    name="browser_tools",
                    params={
                        "command": "uv",
                        "args": ["--directory", str(browser_server_dir), "run", "browser/server.py"],
                    },
                    category="tool",
                    timeout=120,
                    retries=2,
                    semaphore=2,
                )
	# 浏览器智能体
	browser_agent = oxy.ReActAgent(
		name="browser_agent",
		desc="Browser automation agent for web operations and information extraction",
		tools=["browser_tools", "python_tools", "file_tools", "math_tools", "string_tools"],
		prompt=BROWSER_AGENT_PROMPT,
		max_react_rounds=50,  # 增加轮数以确保有足够机会完成任务
		timeout=600,  # 增加超时时间到10分钟
		retries=2,
		semaphore=2,
		is_retain_subagent_in_toolset=False,  # 确保子智能体可以访问工具
	)

	master_agent.sub_agents.append("browser_agent")

	# 注册：将所有组件添加到 oxy_space
	oxy_space = [llm, *tools, time_agent, file_agent, math_agent, multimodal_agent, master_agent, browser_agent, browser_tools]
	return oxy_space


# -----------------------------
# 运行模式
# -----------------------------
async def run_web(mas: MAS, oxy_space: list, first_query: str | None) -> None:
	"""
	启动 Web + SSE 服务，默认展示一个 first_query，便于前端联调与演示。
	"""
	await mas.start_web_service(first_query=first_query or "")


async def run_single_query(mas: MAS, oxy_space: list, query: str | None, file_path: str | None) -> None:
	print(f"\n{'='*60}")
	print("单问题问答模式")
	print(f"问题: {query}")
	print(f"{'='*60}\n")
	try:			
		# 创建请求
		oxy_request = OxyRequest(
			callee="master_agent",
			arguments={"query": query},
			caller_category="user",
		)
		oxy_request.set_mas(mas)
		
		# 使用MAS的chat_with_agent方法，它能更好地处理子智能体调用链
		oxy_response = await mas.chat_with_agent(payload={"query": query})
		
		# 提取答案
		answer = oxy_response.output.strip()
		
		# 如果答案包含解释，尝试提取纯数值（针对"仅输出数值"的要求）
		if "仅输出数值" in query or "仅需输出数值" in query or "仅输出数字" in query:
			import re
			# 尝试提取数值
			numbers = re.findall(r'-?\d+\.?\d*', answer)
			if numbers:
				# 取最后一个数值（通常是最终答案）
				answer = numbers[-1]
		
		print(f"\n{'='*60}")
		print("✓ 处理完成")
		print(f"{'='*60}")
		print(f"\n答案: {answer}\n")
		
		return answer

	except Exception as e:
		print(f"\n✗ 处理失败: {str(e)}")
		import traceback
		traceback.print_exc()
		return ""


async def run_batch(oxy_space: list, data_path: str, return_trace_id: bool) -> None:
	"""
	批处理模式：从 JSONL 或 JSON 加载一组 query，执行并打印结果。
	输入格式支持：
	- JSONL: 每行一个对象，字段至少包含 query
	- JSON : 列表形式的对象数组
	"""
	def load_queries(path: str) -> list[str]:
		p = Path(path)
		if not p.exists():
			raise FileNotFoundError(f"未找到数据文件: {path}")
		if p.suffix.lower() == ".jsonl":
			queries = []
			with p.open("r", encoding="utf-8") as f:
				for line in f:
					line = line.strip()
					if not line:
						continue
					obj = json.loads(line)
					q = obj.get("query", "")
					if q:
						queries.append(q)
			return queries
		elif p.suffix.lower() == ".json":
			with p.open("r", encoding="utf-8") as f:
				data = json.load(f)
			return [item.get("query", "") for item in data if isinstance(item, dict) and item.get("query")]
		else:
			raise ValueError("仅支持 .jsonl 或 .json 输入文件")

	queries = load_queries(data_path)
	async with MAS(oxy_space=oxy_space) as mas:
		results = await mas.start_batch_processing(queries, return_trace_id=return_trace_id)
		# 控制台输出（便于流水线抓取）
		for item in results:
			if isinstance(item, dict):
				print(json.dumps(item, ensure_ascii=False))
			else:
				print(item)


# -----------------------------
# 最小可运行 Demo（单轮）
# -----------------------------
async def run_demo(mas: MAS, oxy_space: list) -> None:
	"""
	最小可运行示例：
	- 询问当前时间并保存到 time.txt
	- 展示工具调用与结果消息在 ES/Redis 中的完整链路（如已启用）
	"""
	first_query = "What time is it now? Please save it into time.txt."
	oxy_response = await mas.chat_with_agent(payload={"query": first_query})
	print(oxy_response.output)


# -----------------------------
# CLI 入口
# -----------------------------
def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="OxyGent-datasci 主程序")
	parser.add_argument(
		"--mode",
		choices=["web", "single", "batch", "demo"],
		default="single",
		help="运行模式：web/single/batch/demo",
	)
	parser.add_argument(
		"--query",
		type=str,
		default=DEFAULT_QUERY,
		help="单次查询（在 single 模式有效；若缺省则进入 REPL）",
	)
	parser.add_argument(
		"--first-query",
		type=str,
		default="What time is it now? Please save it into time.txt.",
		help="Web 模式首页展示的默认问题",
	)
	parser.add_argument(
		"--data",
		type=str,
		default=None,
		help="批处理输入数据路径（.jsonl 或 .json）",
	)
	parser.add_argument(
		"--return-trace-id",
		action="store_true",
		help="批处理是否返回 trace_id（用于离线审计）",
	)
	parser.add_argument(
		"--file_path",
		type=str,
		default=None,
		help="文件路径",
	)
	return parser


async def async_main() -> None:
	setup_env()
	oxy_space = build_oxy_space()

	parser = build_parser()
	args = parser.parse_args()

	async with MAS(oxy_space=oxy_space) as mas:
		await asyncio.sleep(1.0)  # 给工具初始化更多时间
		await check_tool_permisssion(mas, oxy_space)
		if args.mode == "web":
			await run_web(mas, oxy_space, args.first_query)
		elif args.mode == "single":
			await run_single_query(mas, oxy_space, args.query, args.file_path)
		elif args.mode == "batch":
			if not args.data:
				raise SystemExit("batch 模式需要提供 --data 路径（.jsonl 或 .json）")
			await run_batch(mas, oxy_space, args.data, args.return_trace_id)
		else:
			# demo
			await run_demo(mas, oxy_space)


def main() -> None:
	asyncio.run(async_main())


if __name__ == "__main__":
	main()

