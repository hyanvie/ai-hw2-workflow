import json
import logging
import os
import time

END = "__end__"  # 流程结束的标记

log = logging.getLogger("workflow")


class Workflow:
    """一个很小的流程引擎：Agent当节点，边可以带条件。

    从start开始，每跑完一个节点，就按添加顺序检查它的出边，
    第一条条件成立的边就是下一步；没有条件的边永远成立；一条都没命中就结束。
    """

    def __init__(self, name="workflow", max_steps=20, retries=2, retry_wait=1.0):
        self.name = name
        self.max_steps = max_steps  # 防止循环出不来
        self.retries = retries      # 单个节点失败后最多再试几次
        self.retry_wait = retry_wait
        self.agents = {}
        self.edges = {}
        self.start = None

    def add_agent(self, agent):
        self.agents[agent.name] = agent
        if self.start is None:  # 第一个加进来的当起点
            self.start = agent.name
        return self

    def add_edge(self, src, dst, cond=None):
        self.edges.setdefault(src, []).append((dst, cond))
        return self

    def validate(self):
        for src, outs in self.edges.items():
            if src not in self.agents:
                raise ValueError("边的起点不存在: " + src)
            for dst, _ in outs:
                if dst != END and dst not in self.agents:
                    raise ValueError("边的终点不存在: " + dst)

    def _next(self, cur, state):
        for dst, cond in self.edges.get(cur, []):
            if cond is None or cond(state):
                return dst
        return END

    def _run_node(self, name, state, step):
        agent = self.agents[name]
        for attempt in range(1, self.retries + 2):
            t0 = time.time()
            try:
                agent.run(state)
                status, err = "ok", ""
            except Exception as e:  # 网络、JSON解析等问题都走重试
                status, err = "error", "%s: %s" % (type(e).__name__, e)
            cost = round(time.time() - t0, 2)
            state.trace.append(
                {"step": step, "agent": name, "attempt": attempt,
                 "status": status, "seconds": cost, "error": err}
            )
            if status == "ok":
                log.info("step %d  %-9s 完成 (%.2fs)", step, name, cost)
                return True
            log.warning("step %d  %-9s 第%d次失败: %s", step, name, attempt, err)
            if attempt <= self.retries:
                time.sleep(self.retry_wait)
        return False

    def run(self, state):
        self.validate()
        cur, step = self.start, 0
        while cur != END:
            if step >= self.max_steps:
                log.warning("超过最大步数 %d，强制结束", self.max_steps)
                state.set("stopped", "max_steps")
                break
            step += 1
            if not self._run_node(cur, state, step):
                state.set("failed_at", cur)
                break
            cur = self._next(cur, state)
        return state

    def save_log(self, state, log_dir="logs"):
        """把这次运行的记录和最终状态存成json，方便回头查。"""
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, time.strftime("run_%Y%m%d_%H%M%S.json"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"workflow": self.name, "trace": state.trace, "state": state.data},
                      f, ensure_ascii=False, indent=2)
        return path
