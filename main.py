import argparse
import asyncio
import json
import os, sys
from pathlib import Path

from dotenv import load_dotenv
from typing import Dict, List

# OxyGent 入口
from oxygent import MAS, Config, oxy, preset_tools

"""
{"task_id":"d88d3b99-2728-4bd2-9708-8c2637e7a7c4",
"query":"根据pdf内容回答以下问题，假设用户在秒送下单了510元的商品，门店选择了自送模式，最后在超时15个小时的情况下才送达客户，问京东会扣除门店多少钱？输出数值",
"level":"2","file_name":"['hqwqa3.pdf']","answer":"10","steps":"1. 识别pdf中关于门店自送模式的违约条例2.确认超时时间低于24小时且高于60分钟，处罚每单10元。"}
"""

DEFAULT_QUERY = "根据pdf内容回答以下问题，假设用户在秒送下单了510元的商品，门店选择了自送模式，最后在超时15个小时的情况下才送达客户，问京东会扣除门店多少钱？输出数值。"


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

def save_results(results: List[Dict], output_path: str):
    """保存结果到 JSONL 文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"✓ 结果已保存到: {output_path}")


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
	)
	file_agent = oxy.ReActAgent(
		name="file_agent",
		desc="进行本地文件系统读写与管理",
		tools=["file_tools"],
	)
	math_agent = oxy.ReActAgent(
		name="math_agent",
		desc="执行数学计算、表达式求值、表格类数据计算",
		tools=["math_tools"],
	)

	# 新增：为多模态工具创建一个专属智能体
	multimodal_agent = oxy.ReActAgent(
		name="multimodal_agent",
		desc="读取PDF和图片中的文本内容",
		tools=["multimodal_tools"],
	)

	master_agent = oxy.ReActAgent(
		is_master=True,
		name="master_agent",
		desc="多工具编排与子智能体调度的总控智能体",
		# 授权：将 multimodal_agent 添加到主智能体的可调度列表
		sub_agents=["time_agent", "file_agent", "math_agent", "multimodal_agent"],
	)

	# 预设工具实例
	tools = [
		preset_tools.time_tools,
		preset_tools.file_tools,
		preset_tools.math_tools,
		# 注册：将 multimodal_tools 添加到工具列表
		preset_tools.multimodal_tools,
	]

	# 后续五个任务的扩展挂点（示例占位，贡献者可在此处追加）
	# 示例：
	# advanced_retrieval_agent = oxy.ReActAgent(
	# 	name="advanced_retrieval_agent",
	# 	desc="复杂检索与网页浏览工具编排",
	# 	tools=["browser_tools", "retrieve_tools"],
	# )
	# master_agent.sub_agents.append("advanced_retrieval_agent")

	# 注册：将所有组件添加到 oxy_space
	oxy_space = [llm, *tools, time_agent, file_agent, math_agent, multimodal_agent, master_agent]
	return oxy_space


# -----------------------------
# 运行模式
# -----------------------------
async def run_web(oxy_space: list, first_query: str | None) -> None:
	"""
	启动 Web + SSE 服务，默认展示一个 first_query，便于前端联调与演示。
	"""
	async with MAS(oxy_space=oxy_space) as mas:
		await mas.start_web_service(first_query=first_query or "")


async def run_cli(oxy_space: list, query: str | None, file_path: str | None) -> None:
	"""
	CLI 模式：若提供 query 则直接问答一轮；否则进入交互式 REPL。
	"""
	async with MAS(oxy_space=oxy_space) as mas:
		if query:
			if file_path:
				query += f" 相关文件路径: {file_path}"
			oxy_response = await mas.chat_with_agent(payload={"query": query})
			print(oxy_response.output)
		else:
			await mas.start_cli_mode()


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
async def run_demo(oxy_space: list) -> None:
	"""
	最小可运行示例：
	- 询问当前时间并保存到 time.txt
	- 展示工具调用与结果消息在 ES/Redis 中的完整链路（如已启用）
	"""
	first_query = "What time is it now? Please save it into time.txt."
	async with MAS(oxy_space=oxy_space) as mas:
		oxy_response = await mas.chat_with_agent(payload={"query": first_query})
		print(oxy_response.output)


# -----------------------------
# CLI 入口
# -----------------------------
def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="OxyGent-datasci 主程序")
	parser.add_argument(
		"--mode",
		choices=["web", "cli", "batch", "demo"],
		default="cli",
		help="运行模式：web/cli/batch/demo",
	)
	parser.add_argument(
		"--query",
		type=str,
		default=DEFAULT_QUERY,
		help="单次查询（在 cli 模式有效；若缺省则进入 REPL）",
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

	if args.mode == "web":
		await run_web(oxy_space, args.first_query)
	elif args.mode == "cli":
		await run_cli(oxy_space, args.query, args.file_path)
	elif args.mode == "batch":
		if not args.data:
			raise SystemExit("batch 模式需要提供 --data 路径（.jsonl 或 .json）")
		await run_batch(oxy_space, args.data, args.return_trace_id)
	else:
		# demo
		await run_demo(oxy_space)


def main() -> None:
	asyncio.run(async_main())


if __name__ == "__main__":
	main()

