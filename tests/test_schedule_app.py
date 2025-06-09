import unittest
from schedule_app import Schedule

class TestSchedule(unittest.TestCase):
    def setUp(self):
        self.schedule = Schedule()

    def test_add_event(self):
        self.assertTrue(self.schedule.add_event('Meeting'))
        self.assertIn('Meeting', self.schedule.get_events())
        # Adding the same event again should fail
        self.assertFalse(self.schedule.add_event('Meeting'))

    def test_remove_event(self):
        self.schedule.add_event('Call')
        self.assertTrue(self.schedule.remove_event('Call'))
        self.assertNotIn('Call', self.schedule.get_events())
        # Removing an event that does not exist should return False
        self.assertFalse(self.schedule.remove_event('Call'))

    def test_get_events_returns_copy(self):
        self.schedule.add_event('Lunch')
        events = self.schedule.get_events()
        events.append('Dinner')
        self.assertNotIn('Dinner', self.schedule.get_events())

if __name__ == '__main__':
    unittest.main()
