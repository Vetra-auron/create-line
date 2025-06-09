# create-line

This repository hosts a small command-line scheduling app. It lets you create,
list and delete scheduled tasks so you can keep track of upcoming jobs or
reminders.

## Running `schedule_app.py`

Make sure you have Python 3 installed. From the repository root run:

```bash
python schedule_app.py <command> [options]
```

## Command examples

### Add a schedule

```bash
python schedule_app.py add "2023-12-25 14:00" "Send holiday reminder"
```

### List schedules

```bash
python schedule_app.py list
```

### Delete a schedule

```bash
python schedule_app.py delete <schedule-id>
```
