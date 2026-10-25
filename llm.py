import json
import os

import requests

# 默认用智谱的免费模型，接口是OpenAI兼容格式，换别家只改.env就行
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-4.7-flash"


def load_env(path=".env"):
    """很简单的.env读取，不想为这点事多装一个依赖。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class LLM:
    def __init__(self, mock=None):
        load_env()
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = os.getenv("LLM_MODEL", DEFAULT_MODEL)
        # 没配key或者手动指定时走演示模式，这样没网也能跑通流程
        if mock is None:
            mock = (not self.api_key) or os.getenv("LLM_MOCK") == "1"
        self.mock = mock

    def chat(self, role, system, user):
        """role只有演示模式用得到，用来决定返回哪段假数据。"""
        if self.mock:
            return mock_reply(role, user)

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if "bigmodel" in self.base_url:
            # 这个模型默认会先"思考"，关掉能快不少
            body["thinking"] = {"type": "disabled"}

        resp = requests.post(
            self.base_url + "/chat/completions",
            headers={"Authorization": "Bearer " + self.api_key},
            json=body,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ---------- 演示模式用的假数据 ----------
# 故意让第一版代码漏掉 n < 2 的判断，这样能看到 审查->修复->再审查 的循环

BUGGY = '''def is_prime(n):
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True
'''

FIXED = '''def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True
'''


def mock_reply(role, user):
    if role == "coder":
        return "```python\n" + BUGGY + "```"
    if role == "reviewer":
        if "n < 2" in user:
            return json.dumps({"passed": True, "issues": []}, ensure_ascii=False)
        issues = ["没有处理 n < 2 的情况，is_prime(1) 会错误地返回 True"]
        return json.dumps({"passed": False, "issues": issues}, ensure_ascii=False)
    if role == "fixer":
        return "```python\n" + FIXED + "```"
    raise ValueError("演示模式不认识这个角色: " + role)
