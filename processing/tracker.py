from interfaces.tracker import ChangeTracker

'''
trackes most recent seen job
'''
class Tracker(ChangeTracker):
    def __init__(self):
        self._tracker = {}

    def has(self, url):
        return url in self._tracker

    def get(self, url):
        if self.has(url):
            return self._tracker[url]

        return None

    def track(self, url: str, hash_val: str):
        self._tracker[url] = hash_val
