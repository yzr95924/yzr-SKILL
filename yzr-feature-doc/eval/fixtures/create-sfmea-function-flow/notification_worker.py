import json
import time


class Repository:
    def load_pending(self):
        raise NotImplementedError

    def save(self, notifications):
        raise NotImplementedError


class Sender:
    def send(self, notification):
        raise NotImplementedError


def load_config(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def send_batch(repo, sender, config):
    pending = repo.load_pending()
    if not pending:
        return 0

    if __debug__:
        assert config["retry_times"] > 0

    sent = 0
    for notification in pending:
        for _ in range(config["retry_times"]):
            try:
                sender.send(notification)
                notification.status = "sent"
                sent += 1
                break
            except TimeoutError:
                time.sleep(config["retry_interval"])
            except Exception:
                notification.status = "failed"
                break
        else:
            notification.status = "failed"

    repo.save(pending)
    return sent
