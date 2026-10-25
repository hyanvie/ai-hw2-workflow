import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import Agent
from llm import LLM
from main import build_workflow
from state import State
from workflow import END, Workflow


class Add(Agent):
    """测试用的小Agent：往状态里的列表追加自己的名字。"""

    def __init__(self, name):
        super().__init__(None)
        self.name = name

    def run(self, state):
        state.set("path", state.get("path", []) + [self.name])


class Flaky(Agent):
    """前两次调用会报错，第三次才成功，用来测重试。"""

    name = "flaky"

    def __init__(self):
        super().__init__(None)
        self.calls = 0

    def run(self, state):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("临时故障")
        state.set("ok", True)


class WorkflowTest(unittest.TestCase):
    def test_sequential(self):
        wf = Workflow(retry_wait=0)
        wf.add_agent(Add("a")).add_agent(Add("b")).add_agent(Add("c"))
        wf.add_edge("a", "b").add_edge("b", "c")
        state = wf.run(State())
        self.assertEqual(state.get("path"), ["a", "b", "c"])

    def test_condition_branch(self):
        wf = Workflow(retry_wait=0)
        wf.add_agent(Add("a")).add_agent(Add("yes")).add_agent(Add("no"))
        wf.add_edge("a", "yes", lambda s: s.get("flag"))
        wf.add_edge("a", "no")
        self.assertEqual(wf.run(State(flag=True)).get("path"), ["a", "yes"])
        self.assertEqual(wf.run(State(flag=False)).get("path"), ["a", "no"])

    def test_retry_then_success(self):
        flaky = Flaky()
        wf = Workflow(retries=2, retry_wait=0)
        wf.add_agent(flaky)
        state = wf.run(State())
        self.assertTrue(state.get("ok"))
        self.assertEqual(flaky.calls, 3)

    def test_retry_exhausted(self):
        wf = Workflow(retries=1, retry_wait=0)
        wf.add_agent(Flaky())
        state = wf.run(State())
        self.assertEqual(state.get("failed_at"), "flaky")

    def test_max_steps_stops_loop(self):
        wf = Workflow(max_steps=5, retry_wait=0)
        wf.add_agent(Add("a")).add_agent(Add("b"))
        wf.add_edge("a", "b").add_edge("b", "a")  # 死循环
        state = wf.run(State())
        self.assertEqual(state.get("stopped"), "max_steps")
        self.assertEqual(len(state.get("path")), 5)

    def test_bad_edge(self):
        wf = Workflow()
        wf.add_agent(Add("a"))
        wf.add_edge("a", "不存在")
        with self.assertRaises(ValueError):
            wf.run(State())


class CodeReviewFlowTest(unittest.TestCase):
    def test_mock_flow_loops_once(self):
        wf = build_workflow(LLM(mock=True))
        wf.retry_wait = 0
        state = wf.run(State(task="写一个函数 is_prime(n)"))
        names = [t["agent"] for t in state.trace]
        # 第一版有bug：coder -> reviewer -> fixer -> reviewer
        self.assertEqual(names, ["coder", "reviewer", "fixer", "reviewer"])
        self.assertTrue(state.get("review")["passed"])
        self.assertEqual(state.get("round"), 1)

    def test_stops_after_max_rounds(self):
        class AlwaysFail(LLM):
            def chat(self, role, system, user):
                if role == "reviewer":
                    return '{"passed": false, "issues": ["不行"]}'
                return "```python\nx = 1\n```"

        wf = build_workflow(AlwaysFail(mock=True), max_rounds=2)
        wf.retry_wait = 0
        state = wf.run(State(task="随便"))
        self.assertEqual(state.get("round"), 2)
        self.assertFalse(state.get("review")["passed"])
        self.assertIsNone(state.get("failed_at"))


if __name__ == "__main__":
    unittest.main()
