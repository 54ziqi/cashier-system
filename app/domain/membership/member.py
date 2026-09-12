"""领域层：会员值对象/逻辑"""


class MemberLevel:
    """会员等级计算"""
    THRESHOLDS = {
        "diamond": 10000,
        "gold": 5000,
        "silver": 1000,
        "normal": 0,
    }

    @classmethod
    def calculate(cls, points: int) -> str:
        for level, threshold in cls.THRESHOLDS.items():
            if points >= threshold:
                return level
        return "normal"


class Member:
    """会员聚合根"""

    def __init__(self, id: str = "", merchant_id: str = "", card_no: str = "",
                 name: str = "", phone: str = "", balance: int = 0,
                 points: int = 0, level: str = "normal"):
        self.id = id
        self.merchant_id = merchant_id
        self.card_no = card_no
        self.name = name
        self.phone = phone
        self.balance = balance  # 分
        self.points = points
        self.level = level

    def recharge(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("Recharge amount must be positive")
        self.balance += amount

    def deduct_balance(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("Deduct amount must be positive")
        if self.balance < amount:
            raise ValueError(f"Insufficient balance: {self.balance} < {amount}")
        self.balance -= amount

    def add_points(self, points: int) -> None:
        if points > 0:
            self.points += points
            self.level = MemberLevel.calculate(self.points)

    def deduct_points(self, points: int) -> None:
        self.points = max(self.points - points, 0)
        self.level = MemberLevel.calculate(self.points)

    def can_afford(self, amount: int) -> bool:
        return self.balance >= amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "merchant_id": self.merchant_id,
            "card_no": self.card_no,
            "name": self.name,
            "phone": self.phone,
            "balance": self.balance,
            "balance_yuan": round(self.balance / 100, 2),
            "points": self.points,
            "level": self.level,
        }


# 积分兑换比例：每消费 1 元（100 分）得 1 积分
POINTS_PER_YUAN = 1
