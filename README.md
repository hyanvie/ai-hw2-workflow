# 代码审查 Workflow（编码 → 审查 → 修复）

软件工程与项目实践课程 Homework 2。做的是"代码审查流程"这个方向：三个 Agent 配合，一个写代码，一个审查，一个根据审查意见修改，审查不过就回去修，直到通过或者达到最大修复轮数。

没有用 LangChain 之类的框架，是直接调用大模型的 API（OpenAI 兼容格式），流程引擎也是自己写的，一百行左右，在 `workflow.py` 里。

## 环境

- Python 3.8 以上
- 只依赖一个第三方库 `requests`
- 大模型用的是 DeepSeek（`deepseek-chat`）。接口是 OpenAI 兼容格式，换成别家的模型只需要改 `.env`，代码不用动

## 运行步骤

以下命令都在项目根目录（有 `main.py` 的那个文件夹）的终端里执行。

1. 安装依赖

   ```
   pip install -r requirements.txt
   ```

2. 配置 key

   把 `.env.example` 复制一份，改名为 `.env`（Windows 的 cmd 里可以用 `copy .env.example .env`），用记事本打开，把 `LLM_API_KEY=` 后面换成自己的 key。key 在 DeepSeek 开放平台的 API keys 页面创建。`.env` 已经写进了 `.gitignore`，不会被提交。

3. 运行

   ```
   python main.py
   python main.py --task "写一个函数，判断字符串是不是回文"
   ```

   可选参数：

   - `--max-rounds` 最多修复几轮，默认 3
   - `--retries` 单个 Agent 出错后最多重试几次，默认 3
   - `--out` 结果保存目录，默认 `output`
   - `--mock` 演示模式，不调用真实模型

4. 跑测试

   ```
   python -m unittest discover -s tests -v
   ```

## 演示模式

不填 key，或者加 `--mock`，程序会进入演示模式，模型的回复是写死的，不需要联网。其中第一版代码故意漏掉了 `n < 2` 的判断，所以会走一遍 coder → reviewer → fixer → reviewer 的循环。这个模式主要是方便测试和检查流程本身有没有问题。

## 运行结果

用 `deepseek-chat` 实际跑的结果：

```
模式：真实模型 deepseek-chat
需求：写一个函数 is_prime(n)，判断一个整数是否为质数

20:17:47 step 1  coder     完成 (1.83s)
20:17:48 step 2  reviewer  完成 (0.93s)

===== 最终代码 =====
def is_prime(n):
    if n < 2:
        return False
    if n < 4:
        return True
    ...
修复轮数：0，审查结果：通过
```

这个需求比较简单，模型第一版代码就通过了审查，所以没有走到 fixer。循环这条路径是用演示模式和单元测试验证的（`tests/test_workflow.py` 里的 `test_mock_flow_loops_once` 和 `test_stops_after_max_rounds`）。

每次运行后会多出两个文件：

- `output/result.py`：最终的代码
- `logs/run_时间.json`：这次运行的完整记录，包括每一步是哪个 Agent、第几次尝试、耗时、有没有报错，以及最后的状态

## 目录结构

```
main.py              入口，负责把三个Agent和流程接起来
workflow.py          流程引擎（节点、条件边、重试、日志）
agents.py            Agent基类和 Coder / Reviewer / Fixer 三个实现
state.py             Agent之间共享的状态
llm.py               调用大模型，也包含演示模式的假数据
tests/               单元测试
Design.md            设计说明
.env.example         配置模板（真正的 .env 不在提交的文件里）
```

## 关于限流

一开始我用的是智谱的免费模型，晚上经常返回 429（请求太多），重试几次也过不去，所以最后换成了 DeepSeek。代码里对这类问题做了两处处理：出错的 Agent 会按间隔自动重试，另外可以在 `.env` 里设置 `LLM_MIN_INTERVAL`，让两次请求隔开几秒。

## 已知的不足

- 审查主要靠模型判断，只额外做了语法检查（能不能 compile），没有真的去执行代码或者跑测试用例。
- 目前只实现了顺序、条件分支和循环，没有做并行执行，也没有可视化界面。
- 模型的 JSON 输出偶尔格式不对，现在的处理办法是让这个节点重试，没有做更细的容错。

设计思路和扩展方法见 `Design.md`。
