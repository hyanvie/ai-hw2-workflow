import json
import re


def extract_code(text):
    """从模型回复里把```python ... ```里面的代码拿出来，没有代码块就原样返回。"""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def extract_json(text):
    """模型有时会在JSON前后加几句废话，这里只取第一个{到最后一个}。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("审查结果里找不到JSON: " + text[:80])
    return json.loads(m.group(0))


class Agent:
    """所有Agent的基类。新增Agent只要继承它、写好name和run就行。"""

    name = "agent"

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):
        raise NotImplementedError


class CoderAgent(Agent):
    name = "coder"
    SYSTEM = "你是一名Python程序员。根据需求写出完整、可直接运行的代码，只返回一个python代码块，不要写解释。"

    def run(self, state):
        reply = self.llm.chat("coder", self.SYSTEM, "需求：" + state.get("task"))
        state.set("code", extract_code(reply))
        state.set("round", 0)  # 修复轮数从0开始记


class ReviewerAgent(Agent):
    name = "reviewer"
    SYSTEM = (
        "你是一名严格的代码审查员。检查代码是否满足需求，重点看边界情况、逻辑错误和明显的坏写法。"
        '只返回JSON，格式：{"passed": true或false, "issues": ["问题1", "问题2"]}。'
        "没有问题时passed为true，issues为空列表。"
    )

    def run(self, state):
        code = state.get("code")
        issues = []

        # 先做一个不用模型的检查：能不能编译。模型偶尔会放过语法错误
        try:
            compile(code, "<generated>", "exec")
        except SyntaxError as e:
            issues.append("语法错误：第%s行 %s" % (e.lineno, e.msg))

        prompt = "需求：%s\n\n代码：\n```python\n%s\n```" % (state.get("task"), code)
        result = extract_json(self.llm.chat("reviewer", self.SYSTEM, prompt))
        model_passed = bool(result.get("passed"))
        if not model_passed:
            issues += [str(x) for x in result.get("issues", [])]

        state.set("review", {"passed": model_passed and not issues, "issues": issues})


class FixerAgent(Agent):
    name = "fixer"
    SYSTEM = "你是一名Python程序员。根据审查意见修改代码，只返回修改后的完整代码（一个python代码块），不要写解释。"

    def run(self, state):
        issues = "\n".join("- " + x for x in state.get("review")["issues"])
        prompt = "需求：%s\n\n当前代码：\n```python\n%s\n```\n\n审查意见：\n%s" % (
            state.get("task"),
            state.get("code"),
            issues,
        )
        state.set("code", extract_code(self.llm.chat("fixer", self.SYSTEM, prompt)))
        state.set("round", state.get("round", 0) + 1)
