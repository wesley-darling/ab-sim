# domain/entities/driver.py
from dataclasses import dataclass

from ab_sim.domain.entities.geography import Point
from ab_sim.domain.entities.motion import MovePlan, MoveTask


@dataclass
class Driver:
    id: int
    loc: Point
    state: str = "idle"  # "idle" | "to_pickup" | "wait" | "to_dropoff"
    task_id: int = 0
    motion: MovePlan | None = None

    @property
    def current_move(self) -> MoveTask | None:
        if self.motion is None or not self.motion.tasks:
            return None
        # If plan has 1 task, return it; otherwise synthesize an envelope MoveTask
        if len(self.motion.tasks) == 1:
            return self.motion.tasks[0]
        m0, mN = self.motion.tasks[0], self.motion.tasks[-1]
        return MoveTask(
            start=m0.start, end=mN.end, start_t=self.motion.start_t, end_t=self.motion.end_t
        )

    def clear_motion(self) -> None:
        self.motion = None

    def snap_to_plan_end(self) -> None:
        self.loc = self.motion.tasks[-1].end if self.motion else self.loc

    def pos_at(self, t: float) -> Point:
        return self.motion.pos(t) if self.motion else self.loc
