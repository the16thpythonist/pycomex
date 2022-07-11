import time
from typing import List, Tuple, Optional


class AbstractWorkTracker:
    def __init__(self, total_work: int):
        self.total_work = total_work
        self.work_history: List[Tuple[float, float]] = []
        self.remaining_work = 0
        self.remaining_time = 0
        self.eta = 0

        self.start_time: Optional[float] = None

    def set_total_work(self, total_work: int):
        self.total_work = total_work
        self.remaining_work = total_work - len(self.work_history)

    @property
    def completed_work(self):
        return len(self.work_history)

    def start(self) -> None:
        self.start_time = time.time()

    def update(self, n: int = 1, weight: float = 1.0) -> None:
        current_time = time.time()
        for i in range(n):
            self.work_history.append((current_time, weight))

        self.remaining_work -= n

        self.remaining_time = self.estimate()
        self.eta = time.time() + self.remaining_time

    def estimate(self) -> float:
        raise NotImplementedError


class NaiveWorkTracker(AbstractWorkTracker):
    def __init__(self, total_work: int):
        super(NaiveWorkTracker, self).__init__(total_work)

    def estimate(self) -> float:
        # we will simply calculate the average time which all the work packages took and then try to
        # linearly interpolate this average duration for the amount of remaining packages.

        # The first duration, which is measured from start time to first work completion
        durations = [self.work_history[0][0] - self.start_time]

        durations += [self.work_history[i + 1][0] - self.work_history[i][0] for i in range(len(self.work_history) - 1)]
        avg_duration = sum(durations) / len(durations)

        remaining_time = avg_duration * self.remaining_work
        return remaining_time
