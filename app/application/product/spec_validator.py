"""产品规格校验与辅助函数"""

from __future__ import annotations


def validate_spec_selection(
    groups: list[dict], selections: list[dict]
) -> tuple[bool, str]:
    """校验选购是否符合规格组的必选规则。

    Args:
        groups: 规格组列表, 每项包含
            {group_name: str, required: bool, min_select: int, max_select: int}
        selections: 用户选购列表, 每项包含
            {group_name: str, values: list[str]}

    Returns:
        (ok, error_msg)
    """
    if not groups:
        return True, ""

    # 将 selections 转为 {group_name: set(values)} 便于查找
    sel_map: dict[str, set[str]] = {}
    for sel in selections:
        gname = sel.get("group_name", "")
        vals = sel.get("values", [])
        sel_map[gname] = set(vals)

    for grp in groups:
        gname = grp.get("group_name", "")
        required = grp.get("required", False)
        min_select = grp.get("min_select", 1 if required else 0)
        max_select = grp.get("max_select", 1)

        selected_vals = sel_map.get(gname, set())
        count = len(selected_vals)

        if required and count == 0:
            return False, f"规格「{gname}」为必选项"
        if count < min_select:
            return False, f"规格「{gname}」至少选 {min_select} 项"
        if count > max_select:
            return False, f"规格「{gname}」最多选 {max_select} 项"

    return True, ""


def calc_price_delta(
    spec_groups: list[dict], selections: list[dict], options: list[dict] | None = None
) -> int:
    """根据选中选项计算总加价金额（分）。

    Args:
        spec_groups: 规格组定义列表 (用于校验 sélection 合法性)
        selections: 用户选购列表 [{group_name, values: [str]}]
        options: 规格选项列表 [{group_name, value, price_delta}].
            若为 None 则从空表推导 (返回 0)

    Returns:
        总加价金额（分）
    """
    if not selections:
        return 0

    # 校验: 若提供 spec_groups, 先校验选购合法性
    if spec_groups:
        ok, _ = validate_spec_selection(spec_groups, selections)
        if not ok:
            return 0

    # 将选项列表转为 {(group_name, value): price_delta}
    price_map: dict[tuple[str, str], int] = {}
    if options:
        for opt in options:
            key = (opt.get("group_name", ""), opt.get("value", ""))
            price_map[key] = opt.get("price_delta", 0)

    total = 0
    for sel in selections:
        gname = sel.get("group_name", "")
        for val in sel.get("values", []):
            total += price_map.get((gname, val), 0)

    return total


def format_spec_text(selections: list[dict]) -> str:
    """返回人类可读规格文本。

    Args:
        selections: [{group_name: str, values: list[str]}]

    Returns:
        如 '大杯/少冰/三分糖/加珍珠'
    """
    if not selections:
        return ""

    parts: list[str] = []
    for sel in selections:
        vals = sel.get("values", [])
        # 防御: 允许 values 为字符串或列表
        if isinstance(vals, str):
            if vals:
                parts.append(vals)
        else:
            parts.extend(vals)

    return "/".join(parts)
