class Schedule:
    def __init__(self):
        self.events = []

    def add_event(self, event):
        if event not in self.events:
            self.events.append(event)
            return True
        return False

    def remove_event(self, event):
        if event in self.events:
            self.events.remove(event)
            return True
        return False

    def get_events(self):
        return list(self.events)
