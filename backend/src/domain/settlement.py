"""渠道服务费月结：沿用月报确认学员口径，逐人分摊到分。"""

from .analysis import monthly_intakes
from .spec import CHANNELS, PROGRAMS

FEE_FEN = 100  # 每名确认学员的服务费合计：1.00 元 = 100 分


def apportion(total_fen, channels):
    """把 total_fen 均分给 channels（按名册顺序），返回 {channel: 分}。

    最大余数法：先取整商，剩余的分按名册顺序依次补给前列渠道。
    每人合计仍是 total_fen，且各渠道与未取整金额的绝对差之和最小；
    平局固定按名册顺序打破，同一批次重算结果一致。
    """
    count = len(channels)
    base, remainder = divmod(total_fen, count)
    return {channel: base + (1 if index < remainder else 0) for index, channel in enumerate(channels)}


def assess(rows, period):
    """按确认学员口径结算 period 月的服务费。

    返回 (lines, totals, learner_count)：
    - lines：逐人逐渠道的分摊明细（分），按学员编号和渠道名册排序；
    - totals：各渠道该月合计（分）；
    - learner_count：该月确认学员数。
    """
    records, intakes = monthly_intakes(rows)
    eligible = {program: set() for program in PROGRAMS}
    for record in records:
        if record["intake_date"][:7] == period:
            eligible[record["program"]].add(record["channel"])
    order = {channel: index for index, channel in enumerate(CHANNELS)}
    lines = []
    totals = {channel: 0 for channel in CHANNELS}
    learner_count = 0
    for learner, month, _channel, program, converted in intakes:
        if month != period or not converted:
            continue
        learner_count += 1
        channels = sorted(eligible[program], key=order.__getitem__)
        for channel, amount in apportion(FEE_FEN, channels).items():
            lines.append({"learner_id": learner, "channel": channel, "amount_fen": amount})
            totals[channel] += amount
    lines.sort(key=lambda line: (line["learner_id"], order[line["channel"]]))
    return lines, totals, learner_count
