# environment.py
import random
import json
from typing import List, Optional

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message


# ---------------------------------------------------------
# Okoliš ekosustava (grid + resursi + vrijeme)
# ---------------------------------------------------------

class EcosystemEnvironment:
    def __init__(
        self,
        width: int = 10,
        height: int = 10,
        resource_initial: int = 5,
        resource_regen: int = 2,
    ):
        self.width = width
        self.height = height
        self.resource_regen = resource_regen

        self.resources = [
            [resource_initial for _ in range(width)]
            for _ in range(height)
        ]

        self.weather = "sunny"
        self.weather_factor = 1.0

    def randomize_conditions(self):
        possible_weather = {
            "sunny": 1.0,
            "cloudy": 0.95,
            "rainy": 0.85,
            "storm": 0.75,
        }
        self.weather = random.choice(list(possible_weather.keys()))
        self.weather_factor = possible_weather[self.weather]

        for i in range(self.height):
            for j in range(self.width):
                self.resources[i][j] += self.resource_regen

    def consume_resource(self, x: int, y: int, amount: float) -> float:
        available = self.resources[y][x]
        eaten = min(available, amount)
        self.resources[y][x] -= eaten
        return eaten

    def local_resource_level(self, x: int, y: int) -> float:
        return float(self.resources[y][x])


# ---------------------------------------------------------
# SPADE agent okoline
# ---------------------------------------------------------

class EcosystemAgent(Agent):
    def __init__(
        self,
        jid: str,
        password: str,
        prey_jids: List[str],
        predator_jids: List[str],
        resource_regen: int = 2,
    ):
        super().__init__(jid, password)
        self.env = EcosystemEnvironment(resource_regen=resource_regen)
        self.prey_jids = prey_jids
        self.predator_jids = predator_jids
        self.current_day = 0
        self.coach_jid: Optional[str] = None

    class EnvBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if not msg:
                return

            try:
                data = json.loads(msg.body)
            except Exception:
                return

            msg_type = data.get("type")

            if msg_type == "NEW_DAY":
                self.agent.current_day = data["day"]
                self.agent.coach_jid = data["coach_jid"]

                self.agent.env.randomize_conditions()

                info = {
                    "type": "DAY_INFO",
                    "day": self.agent.current_day,
                    "weather": self.agent.env.weather,
                    "weather_factor": self.agent.env.weather_factor,
                    "width": self.agent.env.width,
                    "height": self.agent.env.height,
                    "coach_jid": self.agent.coach_jid,
                }

                for j in self.agent.prey_jids + self.agent.predator_jids:
                    m = Message(to=j)
                    m.body = json.dumps(info)
                    await self.send(m)

                ack = Message(to=self.agent.coach_jid)
                ack.body = json.dumps({
                    "type": "ENV_READY",
                    "day": self.agent.current_day,
                    "weather": self.agent.env.weather,
                    "weather_factor": self.agent.env.weather_factor,
                })
                await self.send(ack)

            elif msg_type == "CONSUME_RESOURCE":
                x = data["x"]
                y = data["y"]
                need = data["need"]
                name = data["name"]
                day = data["day"]

                eaten = self.agent.env.consume_resource(x, y, need)

                reply = Message(to=str(msg.sender))
                reply.body = json.dumps({
                    "type": "RESOURCE_RESULT",
                    "day": day,
                    "eaten": eaten,
                    "name": name,
                })
                await self.send(reply)

            elif msg_type == "PREDATION_EVENT":
                x = data["x"]
                y = data["y"]
                success_prob = data.get("success_prob", 0.7)
                name = data["name"]
                day = data["day"]

                success = random.random() < success_prob

                reply = Message(to=str(msg.sender))
                reply.body = json.dumps({
                    "type": "PREDATION_RESULT",
                    "day": day,
                    "success": success,
                    "name": name,
                    "x": x,
                    "y": y,
                })
                await self.send(reply)

        async def on_end(self):
            print("[ENV] Behaviour završio.")

    async def setup(self):
        print(f"EcosystemAgent startao kao {str(self.jid)}")
        self.add_behaviour(self.EnvBehaviour())
