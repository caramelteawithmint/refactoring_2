import json
from datetime import datetime, timedelta
from enum import Enum, auto
import os
from typing import List, Dict, Optional, Union
from abc import ABC, abstractmethod


class Priority(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()

    def __str__(self):
        return self.name.capitalize()


class TaskStatus(Enum):
    PENDING = auto()
    COMPLETED = auto()
    ARCHIVED = auto()
    DELETED = auto()

    def __str__(self):
        return self.name.capitalize()


class ChangeLog:
    def __init__(self):
        self.changes: List[Dict] = []

    def add_change(self, action: str, task_data: Dict, timestamp: datetime = None):
        entry = {
            "action": action,
            "task_data": task_data,
            "timestamp": timestamp or datetime.now()
        }
        self.changes.append(entry)

    def get_changes_since(self, since: datetime) -> List[Dict]:
        return [change for change in self.changes if change["timestamp"] >= since]

    def to_dict(self) -> List[Dict]:
        return [{
            "action": change["action"],
            "task_data": change["task_data"],
            "timestamp": change["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        } for change in self.changes]

    @classmethod
    def from_dict(cls, data: List[Dict]) -> 'ChangeLog':
        changelog = cls()
        for entry in data:
            changelog.changes.append({
                "action": entry["action"],
                "task_data": entry["task_data"],
                "timestamp": datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
            })
        return changelog


class Notification(ABC):
    @abstractmethod
    def send(self, message: str):
        pass


class ConsoleNotification(Notification):
    def send(self, message: str):
        print(f"Notification: {message}")


class Task:
    def __init__(self, 
                 title: str, 
                 description: str = "", 
                 due_date: datetime = None,
                 priority: Priority = Priority.MEDIUM,
                 category: str = "General"):
        self.title = title
        self.description = description
        self.due_date = due_date
        self.priority = priority
        self.category = category
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.completed_at = None

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()

    def mark_as_completed(self):
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()

    def archive(self):
        self.status = TaskStatus.ARCHIVED
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.strftime("%Y-%m-%d") if self.due_date else None,
            "priority": self.priority.name,
            "category": self.category,
            "status": self.status.name,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": self.completed_at.strftime("%Y-%m-%d %H:%M:%S") if self.completed_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        task = cls(
            title=data["title"],
            description=data.get("description", ""),
            due_date=datetime.strptime(data["due_date"], "%Y-%m-%d") if data.get("due_date") else None,
            priority=Priority[data.get("priority", "MEDIUM")],
            category=data.get("category", "General")
        )
        task.status = TaskStatus[data.get("status", "PENDING")]
        task.created_at = datetime.strptime(data["created_at"], "%Y-%m-%d %H:%M:%S")
        task.updated_at = datetime.strptime(data["updated_at"], "%Y-%m-%d %H:%M:%S")
        if data.get("completed_at"):
            task.completed_at = datetime.strptime(data["completed_at"], "%Y-%m-%d %H:%M:%S")
        return task

    def is_overdue(self) -> bool:
        return (self.due_date and self.due_date < datetime.now() 
                and self.status != TaskStatus.COMPLETED)

    def days_until_due(self) -> Optional[int]:
        if not self.due_date:
            return None
        return (self.due_date - datetime.now()).days


class TaskFilter:
    def __init__(self, 
                 status: Optional[TaskStatus] = None,
                 priority: Optional[Priority] = None,
                 category: Optional[str] = None,
                 overdue_only: bool = False,
                 due_in_days: Optional[int] = None):
        self.status = status
        self.priority = priority
        self.category = category
        self.overdue_only = overdue_only
        self.due_in_days = due_in_days

    def apply(self, tasks: List[Task]) -> List[Task]:
        filtered = tasks
        
        if self.status is not None:
            filtered = [t for t in filtered if t.status == self.status]
        
        if self.priority is not None:
            filtered = [t for t in filtered if t.priority == self.priority]
        
        if self.category is not None:
            filtered = [t for t in filtered if t.category == self.category]
        
        if self.overdue_only:
            filtered = [t for t in filtered if t.is_overdue()]
        
        if self.due_in_days is not None:
            filtered = [t for t in filtered 
                       if t.days_until_due() is not None 
                       and 0 <= t.days_until_due() <= self.due_in_days]
        
        return filtered


class TaskManager:
    def __init__(self, notification: Notification = None):
        self.tasks: List[Task] = []
        self.changelog = ChangeLog()
        self.notification = notification or ConsoleNotification()
        self.load_data()

    def add_task(self, task: Task) -> Task:
        self.tasks.append(task)
        self.changelog.add_change("CREATE", task.to_dict())
        self.save_data()
        self.notification.send(f"Task added: {task.title}")
        return task

    def update_task(self, task_id: int, **kwargs) -> Optional[Task]:
        if 0 <= task_id < len(self.tasks):
            task = self.tasks[task_id]
            old_data = task.to_dict()
            task.update(**kwargs)
            self.changelog.add_change("UPDATE", {
                "old": old_data,
                "new": task.to_dict()
            })
            self.save_data()
            self.notification.send(f"Task updated: {task.title}")
            return task
        return None

    def delete_task(self, task_id: int) -> bool:
        if 0 <= task_id < len(self.tasks):
            task = self.tasks[task_id]
            task.status = TaskStatus.DELETED
            self.changelog.add_change("DELETE", task.to_dict())
            self.save_data()
            self.notification.send(f"Task deleted: {task.title}")
            return True
        return False

    def complete_task(self, task_id: int) -> Optional[Task]:
        if 0 <= task_id < len(self.tasks):
            task = self.tasks[task_id]
            task.mark_as_completed()
            self.changelog.add_change("COMPLETE", task.to_dict())
            self.save_data()
            self.notification.send(f"Task completed: {task.title}")
            return task
        return None

    def archive_task(self, task_id: int) -> Optional[Task]:
        if 0 <= task_id < len(self.tasks):
            task = self.tasks[task_id]
            task.archive()
            self.changelog.add_change("ARCHIVE", task.to_dict())
            self.save_data()
            return task
        return None

    def get_task(self, task_id: int) -> Optional[Task]:
        if 0 <= task_id < len(self.tasks):
            return self.tasks[task_id]
        return None

    def filter_tasks(self, task_filter: TaskFilter) -> List[Task]:
        return task_filter.apply(self.tasks)

    def get_categories(self) -> List[str]:
        return list(set(task.category for task in self.tasks))

    def save_data(self):
        data = {
            "tasks": [task.to_dict() for task in self.tasks],
            "changelog": self.changelog.to_dict()
        }
        with open("task_manager_data.json", "w") as f:
            json.dump(data, f, indent=2)

    def load_data(self):
        if os.path.exists("task_manager_data.json"):
            with open("task_manager_data.json", "r") as f:
                try:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(task_data) for task_data in data.get("tasks", [])]
                    self.changelog = ChangeLog.from_dict(data.get("changelog", []))
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error loading data: {e}")
                    self.tasks = []
                    self.changelog = ChangeLog()

    def get_upcoming_tasks(self, days: int = 7) -> List[Task]:
        return self.filter_tasks(TaskFilter(
            status=TaskStatus.PENDING,
            due_in_days=days
        ))

    def get_overdue_tasks(self) -> List[Task]:
        return self.filter_tasks(TaskFilter(
            status=TaskStatus.PENDING,
            overdue_only=True
        ))


class TaskManagerUI:
    def __init__(self, manager: TaskManager):
        self.manager = manager

    def display_menu(self):
        print("\nTask Manager")
        print("1. Add Task")
        print("2. List Tasks")
        print("3. View Task Details")
        print("4. Update Task")
        print("5. Complete Task")
        print("6. Archive Task")
        print("7. Delete Task")
        print("8. Filter Tasks")
        print("9. View Upcoming Tasks")
        print("10. View Overdue Tasks")
        print("11. View Change Log")
        print("12. Exit")

    def input_task_data(self) -> Dict:
        print("\nEnter Task Details:")
        title = self._get_input("Title: ", required=True)
        description = self._get_input("Description: ")
        due_date = self._get_date_input("Due date (YYYY-MM-DD, optional): ")
        priority = self._get_priority_input()
        category = self._get_input("Category: ", default="General")
        
        return {
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "category": category
        }

    def _get_input(self, prompt: str, required: bool = False, default: str = "") -> str:
        while True:
            value = input(prompt).strip()
            if not value:
                if required:
                    print("This field is required!")
                    continue
                return default
            return value

    def _get_date_input(self, prompt: str) -> Optional[datetime]:
        while True:
            value = input(prompt).strip()
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

    def _get_priority_input(self) -> Priority:
        print("\nPriority:")
        for i, priority in enumerate(Priority):
            print(f"{i+1}. {priority}")
        
        while True:
            choice = input("Select priority (1-4): ")
            if choice.isdigit() and 1 <= int(choice) <= 4:
                return list(Priority)[int(choice)-1]
            print("Invalid choice. Please enter a number between 1 and 4.")

    def display_tasks(self, tasks: List[Task], show_index: bool = True):
        if not tasks:
            print("\nNo tasks found.")
            return
        
        print("\nTasks:")
        for i, task in enumerate(tasks):
            prefix = f"{i+1}. " if show_index else "- "
            status = str(task.status)
            priority = str(task.priority)
            due_date = f" (Due: {task.due_date.strftime('%Y-%m-%d')})" if task.due_date else ""
            overdue = " [OVERDUE]" if task.is_overdue() else ""
            print(f"{prefix}[{status}] [{priority}] {task.title}{due_date}{overdue}")

    def display_task_details(self, task: Task):
        print("\nTask Details:")
        print(f"Title: {task.title}")
        print(f"Description: {task.description}")
        print(f"Status: {task.status}")
        print(f"Priority: {task.priority}")
        print(f"Category: {task.category}")
        if task.due_date:
            print(f"Due Date: {task.due_date.strftime('%Y-%m-%d')}")
            print(f"Days Until Due: {task.days_until_due() or 'N/A'}")
        print(f"Created At: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Updated At: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if task.completed_at:
            print(f"Completed At: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")

    def run(self):
        while True:
            self.display_menu()
            choice = self._get_input("Enter your choice (1-12): ", required=True)
            
            try:
                if choice == "1":
                    task_data = self.input_task_data()
                    task = Task(**task_data)
                    self.manager.add_task(task)
                    print("\nTask added successfully!")
                
                elif choice == "2":
                    tasks = self.manager.tasks
                    self.display_tasks(tasks)
                
                elif choice == "3":
                    task_id = int(self._get_input("Enter task number: ", required=True)) - 1
                    task = self.manager.get_task(task_id)
                    if task:
                        self.display_task_details(task)
                    else:
                        print("\nInvalid task number.")
                
                elif choice == "4":
                    task_id = int(self._get_input("Enter task number to update: ", required=True)) - 1
                    if 0 <= task_id < len(self.manager.tasks):
                        task_data = self.input_task_data()
                        if self.manager.update_task(task_id, **task_data):
                            print("\nTask updated successfully!")
                        else:
                            print("\nFailed to update task.")
                    else:
                        print("\nInvalid task number.")
                
                elif choice == "5":
                    task_id = int(self._get_input("Enter task number to complete: ", required=True)) - 1
                    if self.manager.complete_task(task_id):
                        print("\nTask marked as completed!")
                    else:
                        print("\nInvalid task number.")
                
                elif choice == "6":
                    task_id = int(self._get_input("Enter task number to archive: ", required=True)) - 1
                    if self.manager.archive_task(task_id):
                        print("\nTask archived!")
                    else:
                        print("\nInvalid task number.")
                
                elif choice == "7":
                    task_id = int(self._get_input("Enter task number to delete: ", required=True)) - 1
                    if self.manager.delete_task(task_id):
                        print("\nTask deleted!")
                    else:
                        print("\nInvalid task number.")
                
                elif choice == "8":
                    print("\nFilter Options:")
                    status_choice = self._get_input(
                        "Status (1-Pending, 2-Completed, 3-Archived, 4-Deleted, Enter for all): ")
                    priority_choice = self._get_input(
                        "Priority (1-Low, 2-Medium, 3-High, 4-Critical, Enter for all): ")
                    category = self._get_input("Category (Enter for all): ")
                    
                    status_map = {
                        "1": TaskStatus.PENDING,
                        "2": TaskStatus.COMPLETED,
                        "3": TaskStatus.ARCHIVED,
                        "4": TaskStatus.DELETED
                    }
                    
                    priority_map = {
                        "1": Priority.LOW,
                        "2": Priority.MEDIUM,
                        "3": Priority.HIGH,
                        "4": Priority.CRITICAL
                    }
                    
                    task_filter = TaskFilter(
                        status=status_map.get(status_choice),
                        priority=priority_map.get(priority_choice),
                        category=category if category else None
                    )
                    
                    filtered_tasks = self.manager.filter_tasks(task_filter)
                    self.display_tasks(filtered_tasks)
                
                elif choice == "9":
                    days = int(self._get_input("Show tasks due in how many days? (7): ", default="7"))
                    upcoming_tasks = self.manager.get_upcoming_tasks(days)
                    self.display_tasks(upcoming_tasks)
                
                elif choice == "10":
                    overdue_tasks = self.manager.get_overdue_tasks()
                    self.display_tasks(overdue_tasks)
                
                elif choice == "11":
                    days = int(self._get_input("Show changes from how many days ago? (7): ", default="7"))
                    since = datetime.now() - timedelta(days=days)
                    changes = self.manager.changelog.get_changes_since(since)
                    
                    print(f"\nChange Log (last {days} days):")
                    for change in changes:
                        print(f"\n{change['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} - {change['action']}")
                        if change['action'] == "UPDATE":
                            print("Old values:")
                            print(json.dumps(change['task_data']['old'], indent=2))
                            print("New values:")
                            print(json.dumps(change['task_data']['new'], indent=2))
                        else:
                            print(json.dumps(change['task_data'], indent=2))
                
                elif choice == "12":
                    print("\nGoodbye!")
                    break
                
                else:
                    print("\nInvalid choice. Please enter a number between 1 and 12.")
            
            except Exception as e:
                print(f"\nAn error occurred: {e}")


def main():
    manager = TaskManager()
    ui = TaskManagerUI(manager)
    ui.run()


if __name__ == "__main__":
    main()