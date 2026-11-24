import config
import game_framework
import game_world
from objects import effect
from systems import camera


class AirVent:
    # 숨구멍 (7.2): 벽 틈에서 바람이 새는 곳. 몸이 닿으면 AIR_VENT_REFILL, AIR_VENT_COOLDOWN 뒤 재사용
    # 방 JSON air_vents [x, y, id], (x, y)는 중심. 닿기 처리는 play_mode.check_air_vents
    # 쿨다운은 breath.vent_ready_at[gid] 표에 있다: 방을 나갔다 와도 유지, 저장은 안 함 (docs/숨예산.md 4장)
    # 이끼 동굴(moss) 숨구멍은 이끼가 공기를 내는 곳이라 둘레에 이끼 덩이를 그린다 (2.3, 12.2)
    def __init__(self, room_id, x, y, vent_id, region=None):
        self.x, self.y = x, y
        self.gid = f'{room_id}:{vent_id}'
        self.moss = region == 'moss'
        self.time = 0.0       # 공기 점 애니메이션

    def ready(self):
        from systems import breath   # 순환 import 방지 (world → room → air_vent → breath → world)
        return breath.vent_ready(self.gid)

    def use(self):
        from systems import breath
        breath.use_vent(self.gid)

    def update(self):
        self.time += game_framework.frame_time

    def draw(self):
        if not camera.visible(self.get_bb()):
            return
        color = config.COLOR_AIR_VENT if self.ready() else config.COLOR_AIR_VENT_USED
        if self.moss:
            # 숨구멍 둘레의 이끼 덩이 (쓴 뒤에도 그대로)
            r = config.AIR_VENT_RADIUS
            for dx, dy in config.AIR_VENT_MOSS_TUFTS:
                effect.draw_disc(self.x + dx * r, self.y + dy * r, r * config.AIR_VENT_MOSS_SIZE,
                                 config.COLOR_AIR_VENT_MOSS)
        effect.draw_disc(self.x, self.y, config.AIR_VENT_RADIUS, color)
        if self.ready():
            # 위로 오르는 작은 공기 점 (14.5)
            wind = config.AIR_VENT_WIND
            half = wind['size'] / 2
            for i in range(wind['count']):
                phase = (self.time / wind['period'] + i / wind['count']) % 1
                y = self.y + config.AIR_VENT_RADIUS + phase * wind['rise']
                camera.draw_rect(self.x - half, y - half, self.x + half, y + half, *color, filled=True)
        if game_world.show_hitbox:
            camera.draw_rect(*self.get_bb(), *color)

    def get_bb(self):
        r = config.AIR_VENT_RADIUS
        return self.x - r, self.y - r, self.x + r, self.y + r

    def handle_collision(self, group, other):
        pass
