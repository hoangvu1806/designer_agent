import html
import re
from typing import Any

from .models import UiNode, UiSpecification


COLOR_TOKENS = [
    ("brand/primary", "#DC2626", "Đỏ Cờ Tổ Quốc", "CTA Chính, Nhận diện"),
    ("brand/primary-dark", "#B91C1C", "Đỏ Đậm", "Hover / Focus State"),
    ("brand/primary-deep", "#7F1D1D", "Đỏ Thẫm", "Active / Deep Accent"),
    ("brand/primary-soft", "#FEE2E2", "Hồng Nhạt", "Huy hiệu & Soft Pill"),
    ("brand/primary-tint", "#FEF2F2", "Nền Đỏ Nhạt", "Surface Tint / Highlight"),
    ("accent/gold", "#F59E0B", "Vàng Sao Tổ Quốc", "Ngôi sao, Huy hiệu, Rating"),
    ("accent/gold-soft", "#FEF3C7", "Vàng Nhạt", "Banner khuyến mãi, Tag"),
    ("neutral/slate-900", "#0F172A", "Tiêu đề chính", "Heading 1, Hero Title"),
    ("neutral/slate-800", "#1E293B", "Tiêu đề phụ", "Heading 2, Card Title"),
    ("neutral/slate-600", "#475569", "Nội dung", "Body text, Đoạn văn bản"),
    ("neutral/slate-400", "#94A3B8", "Ghi chú mờ", "Muted, Placeholder, Date"),
    ("neutral/slate-200", "#E2E8F0", "Đường viền", "Borders, Dividers, Card Stroke"),
    ("neutral/slate-50", "#F8FAFC", "Nền trang", "Page Background, Canvas"),
    ("surface/white", "#FFFFFF", "Nền thẻ", "Card Surfaces, Popover"),
    ("status/success", "#10B981", "Xanh lá", "Còn hàng, Đặt hàng thành công"),
    ("status/info", "#0284C7", "Xanh dương", "Hướng dẫn chọn cờ, Hỗ trợ"),
]


def _safe(value: object) -> str:
    text = html.escape(str(value), quote=True)
    return text.replace("{", "&#123;").replace("}", "&#125;")


def _first_text(node: UiNode) -> str:
    for key in ("text", "title", "name", "label", "description", "value"):
        value = node.content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in node.content.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return node.name


def _text_style(node: UiNode, depth: int, is_mobile: bool = False) -> tuple[int, str, str]:
    text_type = str(node.content.get("type", "")).lower()
    level = node.content.get("level")
    name_lower = node.name.lower()
    raw_text = str(node.content.get("text", ""))

    if "description" in name_lower or text_type in ("paragraph", "body", "desc"):
        return 14 if is_mobile else 15, "normal", "#64748B"

    if level == 1 or "hero title" in name_lower or (text_type == "heading" and depth <= 3):
        return 30 if is_mobile else 40, "bold", "#0F172A"
    if level == 2 or "section" in name_lower or (text_type == "heading" and depth == 4):
        return 22 if is_mobile else 28, "bold", "#1E293B"
    if level == 3 or "card title" in name_lower or "product name" in name_lower or "combo name" in name_lower or (text_type == "heading" and depth >= 5):
        return 18 if is_mobile else 20, "bold", "#1E293B"
    if level == 4 or "subtitle" in name_lower or text_type == "subtitle":
        return 15 if is_mobile else 16, "bold", "#334155"

    is_price = text_type == "price" or "price" in name_lower or "giá" in name_lower or "₫" in raw_text or bool(re.search(r"\d+[\.,]?\d*\s*(?:đ|vnd|\$)\b", raw_text, re.IGNORECASE))
    if is_price:
        return 20 if is_mobile else 22, "bold", "#DC2626"
    if "badge" in name_lower or text_type == "badge" or "tag" in name_lower:
        return 12, "bold", "#DC2626"
    if "caption" in name_lower or text_type == "caption" or "meta" in name_lower or "date" in name_lower:
        return 12 if is_mobile else 13, "normal", "#94A3B8"
    if "lead" in name_lower or "tagline" in name_lower:
        return 16 if is_mobile else 18, "normal", "#475569"
    if "link" in name_lower or "nav" in name_lower:
        return 14, "medium", "#334155"
    if "logo" in name_lower:
        return 20 if is_mobile else 24, "bold", "#0F172A"

    return 14 if is_mobile else 15, "normal", "#64748B"


def _component_element(node: UiNode, indent: str, is_mobile: bool = False) -> str:
    slot_id = f"slot::{_safe(node.id)}"
    content = _safe(_first_text(node))
    req = node.requirement
    role = (req.role or "").lower() if req and req.role else ""
    variant = (req.variant_intent or "").lower() if req and req.variant_intent else ""
    name_lower = node.name.lower()

    is_button = role == "button" or "button" in name_lower or "cta" in name_lower or "btn" in name_lower
    is_icon = "icon" in role or "icon" in name_lower
    is_badge = role in ("badge", "tag") or "badge" in name_lower or "tag" in name_lower
    is_input = role in ("input", "textfield") or "input" in name_lower or "search" in name_lower
    is_timer = role in ("timer", "countdown") or "timer" in name_lower or "countdown" in name_lower
    is_codeblock = role in ("codeblock", "code", "coupon") or "code" in name_lower or "promo" in name_lower

    if is_timer:
        return (
            f"{indent}<Frame name=\"{slot_id}\" px={{16}} py={{8}} bg=\"#FEF2F2\" stroke=\"#FECACA\" strokeWidth={{1}} "
            f"rounded={{10}} flex=\"row\" items=\"center\" gap={{8}}>\n"
            f"{indent}  <Text size={{13}} weight=\"bold\" color=\"#DC2626\">⏳ Ưu đãi 2/9 - Còn lại: 02 ngày 14:30:00</Text>\n"
            f"{indent}</Frame>"
        )

    if is_codeblock:
        code_text = node.content.get("code") or content or "QUOCKHANH29"
        return (
            f"{indent}<Frame name=\"{slot_id}\" px={{16}} py={{8}} bg=\"#FFFBEB\" stroke=\"#FDE68A\" strokeWidth={{1}} "
            f"rounded={{10}} flex=\"row\" items=\"center\" gap={{8}}>\n"
            f"{indent}  <Text size={{13}} weight=\"bold\" color=\"#B45309\">✂ Mã giảm giá: {code_text}</Text>\n"
            f"{indent}</Frame>"
        )

    btn_w = " w=\"fill\"" if is_mobile else ""
    btn_h = 48 if is_mobile else 44

    if is_button:
        if variant == "primary" or "buy" in name_lower or "order" in name_lower or "cart" in name_lower or "nhận" in name_lower:
            return (
                f"{indent}<Frame name=\"{slot_id}\"{btn_w} h={{{btn_h}}} px={{24}} bg=\"#DC2626\" rounded={{10}} "
                f"flex=\"row\" items=\"center\" justify=\"center\" gap={{8}}>\n"
                f"{indent}  <Text size={{14}} weight=\"bold\" color=\"#FFFFFF\">{content}</Text>\n"
                f"{indent}</Frame>"
            )
        if variant in ("secondary", "outline") or "view" in name_lower:
            return (
                f"{indent}<Frame name=\"{slot_id}\"{btn_w} h={{{btn_h}}} px={{24}} bg=\"#FFFFFF\" stroke=\"#CBD5E1\" strokeWidth={{1}} "
                f"rounded={{10}} flex=\"row\" items=\"center\" justify=\"center\" gap={{8}}>\n"
                f"{indent}  <Text size={{14}} weight=\"medium\" color=\"#1E293B\">{content}</Text>\n"
                f"{indent}</Frame>"
            )
        return (
            f"{indent}<Frame name=\"{slot_id}\"{btn_w} h={{{btn_h}}} px={{20}} bg=\"#DC2626\" rounded={{10}} "
            f"flex=\"row\" items=\"center\" justify=\"center\" gap={{8}}>\n"
            f"{indent}  <Text size={{14}} weight=\"bold\" color=\"#FFFFFF\">{content}</Text>\n"
            f"{indent}</Frame>"
        )

    if is_icon:
        icon_symbol = "🛒" if "cart" in name_lower else ("🔍" if "search" in name_lower else ("⭐" if "rating" in name_lower or "star" in name_lower else "✦"))
        return (
            f"{indent}<Frame name=\"{slot_id}\" w={{40}} h={{40}} bg=\"#F8FAFC\" stroke=\"#E2E8F0\" strokeWidth={{1}} "
            f"rounded={{20}} flex=\"row\" items=\"center\" justify=\"center\">\n"
            f"{indent}  <Text size={{16}} color=\"#334155\">{icon_symbol}</Text>\n"
            f"{indent}</Frame>"
        )

    if is_badge:
        return (
            f"{indent}<Frame name=\"{slot_id}\" px={{12}} py={{4}} bg=\"#FEF2F2\" stroke=\"#FCA5A5\" strokeWidth={{1}} "
            f"rounded={{999}} flex=\"row\" items=\"center\" gap={{6}}>\n"
            f"{indent}  <Text size={{12}} weight=\"bold\" color=\"#DC2626\">🇻🇳 {content}</Text>\n"
            f"{indent}</Frame>"
        )

    if is_input:
        return (
            f"{indent}<Frame name=\"{slot_id}\" w=\"fill\" h={{44}} px={{16}} bg=\"#FFFFFF\" stroke=\"#CBD5E1\" strokeWidth={{1}} "
            f"rounded={{10}} flex=\"row\" items=\"center\">\n"
            f"{indent}  <Text size={{14}} color=\"#94A3B8\">{content}</Text>\n"
            f"{indent}</Frame>"
        )

    return (
        f"{indent}<Frame name=\"{slot_id}\" w=\"fill\" p={{20}} bg=\"#FFFFFF\" stroke=\"#E2E8F0\" strokeWidth={{1}} "
        f"rounded={{14}} flex=\"col\" justify=\"center\" gap={{8}}>\n"
        f"{indent}  <Text size={{14}} weight=\"bold\" color=\"#1E293B\">{content}</Text>\n"
        f"{indent}</Frame>"
    )


def _media_element(node: UiNode, indent: str, is_mobile: bool = False) -> str:
    name_lower = node.name.lower()
    leaf_id = f"photo::{_safe(node.id)}"
    if "hero" in name_lower or "banner" in name_lower:
        h = 220 if is_mobile else 360
        return f"{indent}<Rectangle name=\"{leaf_id}\" w=\"fill\" h={{{h}}} rounded={{16}} fill=\"#FEF2F2\" stroke=\"#FECACA\" strokeWidth={{1}} />"
    h = 180 if is_mobile else 200
    return f"{indent}<Rectangle name=\"{leaf_id}\" w=\"fill\" h={{{h}}} rounded={{12}} fill=\"#F8FAFC\" stroke=\"#E2E8F0\" strokeWidth={{1}} />"


def _node(node: UiNode, depth: int = 0, is_mobile: bool = False) -> str:
    indent = "  " * depth
    name = _safe(node.name)
    name_lower = node.name.lower()

    if node.kind == "text":
        size, weight, color = _text_style(node, depth, is_mobile)
        content = _safe(_first_text(node))
        name_lower = node.name.lower()
        text_type = str(node.content.get("type", "")).lower()

        is_inline_short = (
            text_type in ("price", "badge", "tag", "icon")
            or "price" in name_lower
            or "giá" in name_lower
            or "badge" in name_lower
            or "tag" in name_lower
            or ("nav" in name_lower and not is_mobile)
            or ("link" in name_lower and not is_mobile)
        )
        w_prop = "" if is_inline_short else " w=\"fill\""
        return (
            f"{indent}<Text name=\"{name}\"{w_prop} size={{{size}}} weight=\"{weight}\" "
            f"color=\"{color}\">{content}</Text>"
        )

    if node.kind == "media":
        return _media_element(node, indent, is_mobile)

    if node.kind == "component":
        return _component_element(node, indent, is_mobile)

    layout = node.layout
    is_grid = any(k in name_lower for k in ("grid", "list", "cards", "features", "products", "guides", "reviews", "benefits", "group", "row", "items")) or (layout and (layout.mode == "grid" or (layout.columns and layout.columns > 1)))
    is_card = not is_grid and any(k in name_lower for k in ("card", "item", "article", "box"))
    is_button_group = any(k in name_lower for k in ("button", "action", "nav", "menu", "link"))

    if is_mobile:
        direction = "row" if ("header" in name_lower or "nav" in name_lower or "action" in name_lower) and not is_grid else "col"
        wrap = ""
    else:
        direction = "row" if (layout and layout.direction == "row") or is_grid else "col"
        wrap = " wrap={true}" if is_grid else ""

    gap = min(layout.gap if layout else 16 if is_mobile else 24, 64)
    padding = min(layout.padding if layout else (16 if is_mobile else (24 if depth else 0)), 80)

    if depth == 0:
        viewport = 390 if is_mobile else 1440
        children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
        return (
            f"{indent}<Frame name=\"{name}\" w={{{viewport}}} h=\"hug\" flex=\"col\" "
            f"gap={{{gap}}} p={{0}} bg=\"#F8FAFC\">\n"
            f"{children}\n{indent}</Frame>"
        )

    if depth == 1:
        is_header = "header" in name_lower or "navbar" in name_lower
        is_footer = "footer" in name_lower
        is_hero = "hero" in name_lower
        pad_x = 20 if is_mobile else 48

        if is_header:
            if is_mobile:
                kept_children = [
                    c for c in node.children
                    if not any(k in c.name.lower() for k in ("nav", "menu", "link", "navigation", "links"))
                ]
                if not kept_children:
                    kept_children = node.children[:1]
                children_str = "\n".join(_node(child, depth + 2, is_mobile) for child in kept_children)
                return (
                    f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"row\" items=\"center\" justify=\"between\" "
                    f"gap={{12}} px={{{pad_x}}} py={{14}} bg=\"#FFFFFF\" stroke=\"#E2E8F0\" strokeWidth={{1}}>\n"
                    f"{indent}  <Frame name=\"Header Left\" flex=\"row\" items=\"center\" gap={{12}}>\n"
                    f"{children_str}\n"
                    f"{indent}  </Frame>\n"
                    f"{indent}  <Frame name=\"Mobile Menu Button\" w={{38}} h={{38}} bg=\"#F8FAFC\" stroke=\"#E2E8F0\" strokeWidth={{1}} "
                    f"rounded={{8}} flex=\"row\" items=\"center\" justify=\"center\">\n"
                    f"{indent}    <Text size={{18}} color=\"#0F172A\">☰</Text>\n"
                    f"{indent}  </Frame>\n"
                    f"{indent}</Frame>"
                )
            children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
            return (
                f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"row\" items=\"center\" justify=\"between\" "
                f"gap={{{gap or 16}}} px={{{pad_x}}} py={{14}} bg=\"#FFFFFF\" stroke=\"#E2E8F0\" strokeWidth={{1}}>\n"
                f"{children}\n{indent}</Frame>"
            )
        if is_footer:
            children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
            return (
                f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"col\" "
                f"gap={{{gap or 24}}} px={{{pad_x}}} py={{{32 if is_mobile else 48}}} bg=\"#0F172A\">\n"
                f"{children}\n{indent}</Frame>"
            )
        if is_hero:
            media_children = [
                c for c in node.children
                if c.kind == "media" or any(k in c.name.lower() for k in ("photo", "image", "media", "banner", "visual"))
            ]
            content_children = [c for c in node.children if c not in media_children]

            if media_children and not is_mobile:
                content_jsx = "\n".join(_node(c, depth + 2, is_mobile) for c in content_children)
                media_jsx = "\n".join(_node(m, depth + 2, is_mobile) for m in media_children)
                return (
                    f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"row\" items=\"center\" justify=\"between\" "
                    f"gap={{48}} px={{{pad_x}}} py={{64}} bg=\"#FFFFFF\">\n"
                    f"{indent}  <Frame name=\"Hero Content\" w={{640}} flex=\"col\" gap={{24}}>\n"
                    f"{content_jsx}\n"
                    f"{indent}  </Frame>\n"
                    f"{indent}  <Frame name=\"Hero Media\" w=\"fill\" h={{380}} flex=\"col\">\n"
                    f"{media_jsx}\n"
                    f"{indent}  </Frame>\n"
                    f"{indent}</Frame>"
                )
            elif media_children and is_mobile:
                content_jsx = "\n".join(_node(c, depth + 2, is_mobile) for c in content_children)
                media_jsx = "\n".join(_node(m, depth + 2, is_mobile) for m in media_children)
                return (
                    f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"col\" items=\"center\" "
                    f"gap={{24}} px={{{pad_x}}} py={{32}} bg=\"#FFFFFF\">\n"
                    f"{indent}  <Frame name=\"Hero Content\" w=\"fill\" flex=\"col\" gap={{16}}>\n"
                    f"{content_jsx}\n"
                    f"{indent}  </Frame>\n"
                    f"{indent}  <Frame name=\"Hero Media\" w=\"fill\" h={{220}} flex=\"col\">\n"
                    f"{media_jsx}\n"
                    f"{indent}  </Frame>\n"
                    f"{indent}</Frame>"
                )
            else:
                children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
                return (
                    f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"col\" items=\"center\" "
                    f"gap={{{gap or 24}}} px={{{pad_x}}} py={{{32 if is_mobile else 64}}} bg=\"#FFFFFF\">\n"
                    f"{children}\n{indent}</Frame>"
                )

        children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
        return (
            f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"col\" "
            f"gap={{{gap or (20 if is_mobile else 32)}}} px={{{pad_x}}} py={{{24 if is_mobile else (padding or 48)}}} bg=\"#FFFFFF\">\n"
            f"{children}\n{indent}</Frame>"
        )

    # depth >= 2:
    if is_grid:
        children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
        return (
            f"{indent}<Frame name=\"{name}\" w=\"fill\" h=\"hug\" flex=\"{direction}\"{wrap} "
            f"gap={{{gap}}} p={{0}} bg=\"transparent\">\n"
            f"{children}\n{indent}</Frame>"
        )

    if is_card:
        bg = "#FFFFFF"
        stroke = " stroke=\"#E2E8F0\" strokeWidth={1}"
        rounded = " rounded={14}" if is_mobile else " rounded={16}"
        p = 16 if is_mobile else 24
        if is_mobile:
            w_attr = " w=\"fill\""
        else:
            w_attr = " w={300}" if any(k in name_lower for k in ("product", "combo", "flag", "guide", "item", "4")) else " w={410}"
        children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
        return (
            f"{indent}<Frame name=\"{name}\"{w_attr} h=\"hug\" flex=\"col\" "
            f"gap={{{gap}}} p={{{p}}} bg=\"{bg}\"{stroke}{rounded}>\n"
            f"{children}\n{indent}</Frame>"
        )

    if is_button_group:
        bg = "transparent"
        stroke = ""
        rounded = ""
        p = 0
        w_attr = " w=\"fill\"" if is_mobile else " w=\"hug\""
    else:
        bg = "transparent"
        stroke = ""
        rounded = ""
        p = 0
        w_attr = " w=\"fill\""

    children = "\n".join(_node(child, depth + 1, is_mobile) for child in node.children)
    return (
        f"{indent}<Frame name=\"{name}\"{w_attr} h=\"hug\" flex=\"{direction}\"{wrap} "
        f"gap={{{gap}}} p={{{p}}} bg=\"{bg}\"{stroke}{rounded}>\n"
        f"{children}\n{indent}</Frame>"
    )


def compile_jsx(specification: UiSpecification, mode: str = "desktop") -> str:
    is_mobile = mode == "mobile" or specification.platform == "mobile"
    return _node(specification.root, is_mobile=is_mobile)


def compile_palette_jsx(screen_name: str) -> str:
    groups = [
        (
            "1. Brand & Primary Colors (Màu chủ đạo)",
            "Màu sắc nhận diện thương hiệu cốt lõi, cờ Tổ quốc, nút bấm CTA chính",
            COLOR_TOKENS[0:5],
        ),
        (
            "2. Secondary & Accents (Màu điểm nhấn)",
            "Màu ngôi sao vàng 5 cánh, huy hiệu ưu đãi và đánh giá xếp hạng",
            COLOR_TOKENS[5:7],
        ),
        (
            "3. Neutrals & Typography (Nền & Văn bản)",
            "Hệ thống màu sắc cho chữ, phân cấp nội dung và nền canvas",
            COLOR_TOKENS[7:14],
        ),
        (
            "4. Status & Semantics (Màu trạng thái)",
            "Phản hồi trạng thái giao dịch, hướng dẫn và thông tin hỗ trợ",
            COLOR_TOKENS[14:16],
        ),
    ]

    sections_jsx = []
    for title, subtitle, tokens in groups:
        swatches_jsx = []
        for token_name, hex_val, label, desc in tokens:
            stroke_attr = " stroke=\"#E2E8F0\" strokeWidth={1}" if hex_val.upper() in ("#FFFFFF", "#F8FAFC", "#FEF2F2", "#FEF3C7", "#FEE2E2") else ""
            swatches_jsx.append(
                f"      <Frame name=\"{label}\" w={{220}} p={{16}} bg=\"#FFFFFF\" stroke=\"#E2E8F0\" strokeWidth={{1}} rounded={{16}} flex=\"col\" gap={{12}}>\n"
                f"        <Rectangle name=\"{label} Swatch\" w=\"fill\" h={{90}} rounded={{10}} fill=\"{hex_val}\"{stroke_attr} />\n"
                f"        <Frame w=\"fill\" flex=\"col\" gap={{4}}>\n"
                f"          <Text size={{14}} weight=\"bold\" color=\"#0F172A\">{label}</Text>\n"
                f"          <Text size={{12}} weight=\"medium\" color=\"#64748B\">{hex_val}</Text>\n"
                f"          <Text size={{11}} color=\"#94A3B8\">{desc}</Text>\n"
                f"        </Frame>\n"
                f"      </Frame>"
            )
        cards_str = "\n".join(swatches_jsx)
        sections_jsx.append(
            f"  <Frame name=\"{title}\" w=\"fill\" flex=\"col\" gap={{16}}>\n"
            f"    <Frame w=\"fill\" flex=\"col\" gap={{4}}>\n"
            f"      <Text size={{20}} weight=\"bold\" color=\"#1E293B\">{title}</Text>\n"
            f"      <Text size={{14}} color=\"#64748B\">{subtitle}</Text>\n"
            f"    </Frame>\n"
            f"    <Frame name=\"Grid\" w=\"fill\" flex=\"row\" wrap={{true}} gap={{16}}>\n"
            f"{cards_str}\n"
            f"    </Frame>\n"
            f"  </Frame>"
        )

    all_sections = "\n".join(sections_jsx)
    return (
        f"<Frame name=\"Color System Artboard\" w={{1440}} h=\"hug\" p={{64}} bg=\"#F8FAFC\" flex=\"col\" gap={{40}}>\n"
        f"  <Frame name=\"Board Header\" w=\"fill\" flex=\"col\" gap={{8}}>\n"
        f"    <Text size={{36}} weight=\"bold\" color=\"#0F172A\">🎨 Design System — Bảng Màu Sắc</Text>\n"
        f"    <Text size={{16}} color=\"#64748B\">Hệ thống màu sắc nhận diện chuẩn hóa, biến màu và tỷ lệ tương phản cho {_safe(screen_name)}</Text>\n"
        f"  </Frame>\n"
        f"{all_sections}\n"
        f"</Frame>"
    )
