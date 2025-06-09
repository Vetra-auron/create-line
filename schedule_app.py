import sys
import json
import os

SCHEDULE_FILE = 'schedule.json'

def load_data():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_data(data):
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_event(date, time_str, description):
    data = load_data()
    next_id = max([item['id'] for item in data], default=0) + 1
    data.append({'id': next_id, 'date': date, 'time': time_str, 'description': description})
    save_data(data)
    print(f"Added event {next_id}.")


def list_events(date):
    data = load_data()
    events = [item for item in data if item['date'] == date]
    if not events:
        print('No events found.')
    else:
        for item in events:
            print(f"{item['id']}: {item['time']} {item['description']}")


def delete_event(event_id):
    data = load_data()
    new_data = [item for item in data if item['id'] != event_id]
    if len(new_data) == len(data):
        print('Event not found.')
    else:
        save_data(new_data)
        print(f"Deleted event {event_id}.")


def main():
    if len(sys.argv) < 2:
        print('Usage: add <date> <time> <description> | list <date> | delete <id>')
        return

    cmd = sys.argv[1]

    if cmd == 'add' and len(sys.argv) >= 5:
        date = sys.argv[2]
        time_str = sys.argv[3]
        description = ' '.join(sys.argv[4:])
        add_event(date, time_str, description)
    elif cmd == 'list' and len(sys.argv) == 3:
        list_events(sys.argv[2])
    elif cmd == 'delete' and len(sys.argv) == 3:
        try:
            event_id = int(sys.argv[2])
        except ValueError:
            print('ID must be an integer.')
            return
        delete_event(event_id)
    else:
        print('Invalid command or arguments.')


if __name__ == '__main__':
    main()
