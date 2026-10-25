class State:
    """所有Agent共用的状态。

    说白了就是一个字典加一份执行记录。Agent之间不直接互相调用，
    都是往这里读、往这里写，所以以后加新Agent不用改旧Agent。
    """

    def __init__(self, **init):
        self.data = dict(init)
        self.trace = []  # 每执行一次Agent就记一条

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
