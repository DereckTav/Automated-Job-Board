from LocalData.tracker import WebTracker

def test_singleton():
    tracker1 = WebTracker()
    tracker2 = WebTracker()

    assert tracker1 is tracker2