from types import SimpleNamespace

from notification_worker import send_batch


class FakeRepository:
    def __init__(self, notifications):
        self.notifications = notifications
        self.saved = None

    def load_pending(self):
        return self.notifications

    def save(self, notifications):
        self.saved = notifications


class FakeSender:
    def __init__(self):
        self.sent = []

    def send(self, notification):
        self.sent.append(notification)


def make_notification():
    return SimpleNamespace(status="pending")


def test_send_batch_success():
    notifications = [make_notification(), make_notification()]
    repo = FakeRepository(notifications)
    sender = FakeSender()

    sent = send_batch(repo, sender, {"retry_times": 3, "retry_interval": 0})

    assert sent == 2
    assert sent == len(sender.sent)
    assert repo.saved == notifications
    assert all(item.status == "sent" for item in notifications)


def test_send_empty_batch():
    repo = FakeRepository([])

    assert send_batch(repo, FakeSender(), {"retry_times": 3, "retry_interval": 0}) == 0
