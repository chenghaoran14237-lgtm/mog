"""
简单的任务worker，用于处理pending状态的任务
"""
import time
from sqlalchemy import text
from app.core.db import SessionLocal
from app.tasks.runner import run_task
from app.core.observability import log_event


def run_worker(poll_interval: int = 2, max_tasks_per_cycle: int = 10):
    """
    轮询pending任务并执行

    Args:
        poll_interval: 轮询间隔（秒）
        max_tasks_per_cycle: 每个周期最多处理的任务数
    """
    print(f"[Worker] 启动任务worker，轮询间隔: {poll_interval}秒")

    while True:
        try:
            session = SessionLocal()
            try:
                # 查询pending任务
                result = session.execute(
                    text("""
                        SELECT id, request_id
                        FROM tasks
                        WHERE status = 'pending'
                        ORDER BY priority DESC, id ASC
                        LIMIT :limit
                    """),
                    {"limit": max_tasks_per_cycle}
                )
                tasks = result.fetchall()

                if tasks:
                    print(f"[Worker] 找到 {len(tasks)} 个pending任务")

                for task_id, request_id in tasks:
                    print(f"[Worker] 执行任务 {task_id}...")
                    try:
                        # 不传database_url，直接使用SessionLocal
                        run_task(task_id, request_id, database_url=None)
                        print(f"[Worker] ✓ 任务 {task_id} 执行完成")
                    except Exception as e:
                        print(f"[Worker] ✗ 任务 {task_id} 执行失败: {e}")
                        log_event("worker_task_failed", task_id=task_id, error=str(e))

            finally:
                session.close()

        except Exception as e:
            print(f"[Worker] 轮询出错: {e}")

        time.sleep(poll_interval)


if __name__ == "__main__":
    run_worker()
