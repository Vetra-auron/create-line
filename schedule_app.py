#!/usr/bin/env python3
import argparse
import json
import os

DB_FILE = 'schedule.json'


def load_data():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_task(task):
    data = load_data()
    data.append(task)
    save_data(data)
    print(f'추가됨: {task}')


def list_tasks():
    data = load_data()
    if not data:
        print('등록된 일정이 없습니다.')
        return
    for idx, t in enumerate(data, 1):
        print(f'{idx}. {t}')


def remove_task(number):
    data = load_data()
    index = number - 1
    if 0 <= index < len(data):
        removed = data.pop(index)
        save_data(data)
        print(f'삭제됨: {removed}')
    else:
        print('존재하지 않는 번호입니다.')


def clear_tasks():
    save_data([])
    print('모든 일정이 삭제되었습니다.')


def main():
    parser = argparse.ArgumentParser(description='간단한 일정 관리 프로그램')
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser('add', help='새 일정 추가')
    add_parser.add_argument('task', help='추가할 일정 내용')

    subparsers.add_parser('list', help='일정 목록 확인')

    remove_parser = subparsers.add_parser('remove', help='일정 삭제')
    remove_parser.add_argument('number', type=int, help='삭제할 일정 번호')

    subparsers.add_parser('clear', help='모든 일정 삭제')

    args = parser.parse_args()

    if args.command == 'add':
        add_task(args.task)
    elif args.command == 'list':
        list_tasks()
    elif args.command == 'remove':
        remove_task(args.number)
    elif args.command == 'clear':
        clear_tasks()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
