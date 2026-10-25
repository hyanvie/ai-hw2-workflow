import argparse
import logging
import os
import sys

from agents import CoderAgent, FixerAgent, ReviewerAgent
from llm import LLM
from state import State
from workflow import END, Workflow

DEFAULT_TASK = "写一个函数 is_prime(n)，判断一个整数是否为质数"


def build_workflow(llm, max_rounds=3):
    wf = Workflow("code-review", retries=5, retry_wait=8)
    wf.add_agent(CoderAgent(llm))      # 第一个加的就是起点
    wf.add_agent(ReviewerAgent(llm))
    wf.add_agent(FixerAgent(llm))

    wf.add_edge("coder", "reviewer")
    # 审查通过，或者已经修了max_rounds轮还不过，就收工
    wf.add_edge("reviewer", END,
                lambda s: s.get("review")["passed"] or s.get("round") >= max_rounds)
    wf.add_edge("reviewer", "fixer")   # 上面没命中就去修
    wf.add_edge("fixer", "reviewer")   # 修完回去再审，形成循环
    return wf


def main():
    # Windows的终端有时不是utf-8，先处理一下，免得中文乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="编码->审查->修复 Workflow")
    parser.add_argument("--task", default=DEFAULT_TASK, help="要让Agent完成的编程需求")
    parser.add_argument("--mock", action="store_true", help="演示模式，不调用真实模型")
    parser.add_argument("--max-rounds", type=int, default=3, help="最多修复几轮")
    parser.add_argument("--out", default="output", help="结果保存目录")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    llm = LLM(mock=True if args.mock else None)
    print("模式：%s" % ("演示(mock)" if llm.mock else "真实模型 " + llm.model))
    print("需求：" + args.task + "\n")

    wf = build_workflow(llm, args.max_rounds)
    state = wf.run(State(task=args.task))

    os.makedirs(args.out, exist_ok=True)
    code_path = os.path.join(args.out, "result.py")
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(state.get("code", "") + "\n")
    log_path = wf.save_log(state)

    review = state.get("review", {})
    print("\n===== 最终代码 =====")
    print(state.get("code", "(没有生成代码)"))
    print("===================")
    if state.get("failed_at"):
        print("流程在 %s 节点失败了，日志见 %s" % (state.get("failed_at"), log_path))
    else:
        print("修复轮数：%d，审查结果：%s" % (state.get("round", 0), "通过" if review.get("passed") else "未通过"))
        print("代码已保存到 %s，运行日志 %s" % (code_path, log_path))


if __name__ == "__main__":
    main()
