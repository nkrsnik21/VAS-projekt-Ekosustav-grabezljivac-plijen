import json
import random
from typing import List

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from entities import Prey


class PreySPAgent(Agent):
    def __init__(self, jid: str, password: str, num_prey: int):
        super().__init__(jid, password)
        self.prey_list: List[Prey] = [
            Prey(
                name=f"Plijen{i}",
                x=random.randint(0, 9),
                y=random.randint(0, 9),
            )
            for i in range(1, num_prey + 1)
        ]

    class PreyBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if not msg:
                return

            try:
                data = json.loads(msg.body)
            except Exception:
                return

            msg_type = data.get("type")

            if msg_type == "DAY_INFO":
                day = data["day"]
                coach_jid = data["coach_jid"]
                env_jid = "ekosustav2@xmpp.jp"
                width = data.get("width", 10)
                height = data.get("height", 10)
                weather_factor = data["weather_factor"]

                new_preys: List[Prey] = []

                for prey in self.agent.prey_list:
                    if not prey.alive:
                        continue

                    local_resources = random.uniform(3, 10)
                    predator_nearby = random.random() < (
                        0.25 * (1.0 / max(weather_factor, 0.1))
                    )

                    action = prey.decide_action(
                        local_resources=local_resources,
                        predator_nearby=predator_nearby,
                    )

                    if action == "move":
                        prey.move(width, height)
                    elif action == "rest":
                        prey.rest()
                    elif action == "feed":
                        req = Message(to=env_jid)
                        req.body = json.dumps(
                            {
                                "type": "CONSUME_RESOURCE",
                                "day": day,
                                "x": prey.x,
                                "y": prey.y,
                                "need": 4.0,
                                "name": prey.name,
                            }
                        )
                        await self.send(req)
                    elif action == "reproduce":
                        child = prey.try_reproduce()
                        if child is not None:
                            new_preys.append(child)

                    prey.age_and_check_death()

                    reply = Message(to=coach_jid)
                    reply.body = json.dumps(
                        {
                            "type": "DAY_RESULT",
                            "role": "prey",
                            "day": day,
                            "name": prey.name,
                            "x": prey.x,
                            "y": prey.y,
                            "energy": prey.energy,
                            "age": prey.age,
                            "alive": prey.alive,
                            "action": action,
                        }
                    )
                    await self.send(reply)

                self.agent.prey_list.extend(new_preys)

            elif msg_type == "RESOURCE_RESULT":
                name = data["name"]
                eaten = data["eaten"]
                for prey in self.agent.prey_list:
                    if prey.name == name and prey.alive:
                        prey.energy += eaten
                        prey.after_feed()
                        break

            elif msg_type == "PREY_KILL_NEAR":
                x = data["x"]
                y = data["y"]
                radius = data.get("radius", 1)

                for prey in self.agent.prey_list:
                    if not prey.alive:
                        continue
                    if abs(prey.x - x) <= radius and abs(prey.y - y) <= radius:
                        prey.alive = False
                        break

    async def setup(self):
        print(
            f"PreySPAgent startao kao {str(self.jid)}, broj plijenova={len(self.prey_list)}"
        )
        self.add_behaviour(self.PreyBehaviour())