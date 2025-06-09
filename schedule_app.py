import json
import os
import argparse
from datetime import datetime

DB_FILE = 'schedule.json'


def load_schedule():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def save_schedule(items):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2)


def add_item(dt_str, description):
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
    except ValueError:
        print('Invalid datetime format. Use YYYY-MM-DD HH:MM')
        return
    items = load_schedule()
    next_id = max((item['id'] for item in items), default=0) + 1
    items.append({
        'id': next_id,
        'datetime': dt.strftime('%Y-%m-%d %H:%M'),
        'description': description
    })
    save_schedule(items)
    print(f'Added item #{next_id}.')


def list_items(date_str):
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        print('Invalid date format. Use YYYY-MM-DD')
        return
    items = load_schedule()
    filtered = []
    for item in items:
        try:
            item_dt = datetime.strptime(item['datetime'], '%Y-%m-%d %H:%M')
        except ValueError:
            continue
        if item_dt.date() == day:
            filtered.append(item)
    if not filtered:
        print('No items found.')
        return
    for item in sorted(filtered, key=lambda x: x['datetime']):
        print(f"{item['id']}: {item['datetime']} - {item['description']}")


def delete_item(item_id):
    items = load_schedule()
    for i, item in enumerate(items):
        if item['id'] == item_id:
            items.pop(i)
            save_schedule(items)
            print(f'Deleted item #{item_id}.')
            return
    print(f'Item #{item_id} not found.')


def main():
    parser = argparse.ArgumentParser(description='Schedule manager')
    subparsers = parser.add_subparsers(dest='command')

    add_p = subparsers.add_parser('add', help='Add a schedule item')
    add_p.add_argument('datetime', help='Date and time in YYYY-MM-DD HH:MM')
    add_p.add_argument('description', help='Item description')

    list_p = subparsers.add_parser('list', help='List items for a day')
    list_p.add_argument('date', help='Date in YYYY-MM-DD')

    del_p = subparsers.add_parser('delete', help='Delete an item by ID')
    del_p.add_argument('id', type=int, help='ID of item to delete')

    args = parser.parse_args()

    if args.command == 'add':
        add_item(args.datetime, args.description)
    elif args.command == 'list':
        list_items(args.date)
    elif args.command == 'delete':
        delete_item(args.id)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
