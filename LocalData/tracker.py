class WebTracker:
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(cls, '_initialized'):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._tracker = {}
            self._initialized = True

    def has(self, url):
        return url in self._tracker

    def get(self, url):
        if self.has(url):
            return self._tracker[url]

        return None

    def track(self, url: str, hash_val: str):
        self._tracker[url] = hash_val
