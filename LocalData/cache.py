from Robots.robots import RobotsRules

class Cache:
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(cls, '_initialized'):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._cache = {}
            self._initialized = True

    def has(self, url):
        return url in self._cache

    def get(self, url):
        if self.has(url):
            return self._cache[url]

        return None

    def cache(self, url: str, rules: RobotsRules):
        self._cache[url] = rules

    def keys(self):
        return self._cache.keys()

    def pop(self, url) -> None:
        self._cache.pop(url, None)