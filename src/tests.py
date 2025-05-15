import pytest
from datetime import datetime, timedelta
from main_ref2 import Task, Priority, TaskStatus, TaskFilter, TaskManager, ChangeLog

@pytest.fixture
def sample_task():
    return Task("Test task", due_date=datetime.now() + timedelta(days=1))

@pytest.fixture
def task_manager():
    manager = TaskManager()
    manager.tasks = [
        Task("Task 1", priority=Priority.HIGH),
        Task("Task 2", status=TaskStatus.COMPLETED),
        Task("Task 3", due_date=datetime.now() - timedelta(days=1))
    ]
    return manager

class TestTask:
    def test_task_creation(self, sample_task):
        assert sample_task.title == "Test task"
        assert sample_task.status == TaskStatus.PENDING
        assert sample_task.priority == Priority.MEDIUM

    def test_mark_completed(self, sample_task):
        sample_task.mark_as_completed()
        assert sample_task.status == TaskStatus.COMPLETED
        assert sample_task.completed_at is not None

    def test_overdue(self):
        task = Task("Overdue", due_date=datetime.now() - timedelta(days=1))
        assert task.is_overdue()

class TestTaskFilter:
    def test_filter_by_status(self, task_manager):
        filtered = TaskFilter(status=TaskStatus.COMPLETED).apply(task_manager.tasks)
        assert len(filtered) == 1
        assert filtered[0].title == "Task 2"

    def test_filter_overdue(self, task_manager):
        filtered = TaskFilter(overdue_only=True).apply(task_manager.tasks)
        assert len(filtered) == 1
        assert filtered[0].title == "Task 3"

class TestTaskManager:
    def test_add_task(self):
        manager = TaskManager()
        task = manager.add_task(Task("New task"))
        assert len(manager.tasks) == 1
        assert manager.changelog.changes[-1]["action"] == "CREATE"

    def test_complete_task(self, task_manager):
        task_manager.complete_task(0)
        assert task_manager.tasks[0].status == TaskStatus.COMPLETED
        assert task_manager.changelog.changes[-1]["action"] == "COMPLETE"

class TestChangeLog:
    def test_add_change(self):
        log = ChangeLog()
        log.add_change("TEST", {"key": "value"})
        assert len(log.changes) == 1
        assert log.changes[0]["action"] == "TEST"