
import random
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SceneObject:
    id: int
    name: str
    type: str
    x: float
    y: float
    z: float
    action: str = "spawn"

class SceneGenerator:
    def __init__(self):
        self.object_pool = {
            "corpse": [1001, 1002, 1003],
            "chest": [2001, 2002],
            "camp_fire": [3001],
            "mysterious_orb": [9999]
        }

    def generate_scene(self, target_x: float, target_y: float, size: float = 5.0) -> List[SceneObject]:
        """Generates a small batch of objects around a target point."""
        objects = []
        num_to_spawn = random.randint(1, 3)

        for _ in range(num_to_spawn):
            obj_type = random.choice(list(self.object_pool.keys()))
            obj_id = random.choice(self.object_pool[obj_type])
            name = obj_type.replace("_", " ").capitalize()

            # Place near target with slight randomization
            spawn_x = target_x + (random.random() - 0.5) * size
            spawn_y = target_y + (random.random() - 0.5) * size

            objects.append(SceneObject(
                id=obj_id,
                name=name,
                type=obj_type,
                x=spawn_x,
                y=spawn_y,
                z=0.0
            ))
        return objects

# Unit test
if __name__ == "__main__":
    gen = SceneGenerator()
    scene = gen.generate_scene(100, 100)
    print(f"Generated scene: {scene}")
