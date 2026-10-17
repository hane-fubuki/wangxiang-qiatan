"""Bounded lossless detail views for CLI vision, whose overview is downscaled.

Original inputs are retained. Crops are additional evidence, never replacements
or enlarged reconstructions. No files, external services, or OCR are involved.
"""
from __future__ import annotations

from io import BytesIO
import json
import math
import re

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.codex_provider import CodexCancelled, CodexError


DETAIL_EDGE = 2048
DETAIL_CROP_LIMIT = 4


def _question_data(prompt: str) -> tuple[str, bool]:
    """Read current question plus the engine's explicit selection marker."""
    block = re.search(r"<visual_question_data>\s*([\s\S]*?)\s*</visual_question_data>", prompt)
    text = block.group(1) if block else prompt.strip()
    if block or text.startswith("{"):
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            return "", False
        if not isinstance(value, dict) or not isinstance(value.get("question"), str):
            return "", False
        return value["question"], value.get("imagesAlreadySelected") is True
    return text, False


def current_question(prompt: str) -> str:
    """Read only the question field, never directional terms from history."""
    return _question_data(prompt)[0]


def _axis_positions(size: int) -> list[int]:
    if size <= DETAIL_EDGE:
        return [0]
    count = math.ceil(size / DETAIL_EDGE)
    return [round(index * (size - DETAIL_EDGE) / (count - 1)) for index in range(count)]


def _regions(question: str) -> list[tuple[str, str]]:
    """Explicit image directions, ordered by occurrence in the current request."""
    patterns = [
        (r"左上(?:角|方|部)?|(?:top|upper)[ -]?left", ("left", "top")),
        (r"右上(?:角|方|部)?|(?:top|upper)[ -]?right", ("right", "top")),
        (r"左下(?:角|方|部)?|(?:bottom|lower)[ -]?left", ("left", "bottom")),
        (r"右下(?:角|方|部)?|(?:bottom|lower)[ -]?right", ("right", "bottom")),
        (r"左(?:侧|边|半边|半部分)|\bleft(?: side| edge| half)?\b", ("left", "any")),
        (r"右(?:侧|边|半边|半部分)|\bright(?: side| edge| half)?\b", ("right", "any")),
        (r"上(?:方|边|部|半部分)|顶部|\b(?:top|upper)(?: side| edge| half)?\b", ("any", "top")),
        (r"下(?:方|边|部|半部分)|底部|\b(?:bottom|lower)(?: side| edge| half)?\b", ("any", "bottom")),
        (r"中间|中央|中心|正中|\bcent(?:er|re)(?: part)?\b", ("center", "center")),
    ]
    matches = []
    for pattern, region in patterns:
        matches.extend((match.start(), match.end(), region) for match in re.finditer(pattern, question, re.I))
    # A corner phrase supersedes its component side words in English.
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    result, covered_until = [], -1
    for start, end, region in matches:
        if start < covered_until:
            continue
        covered_until = end
        if region not in result:
            result.append(region)
    return result


def _boxes(width: int, height: int, regions) -> list[tuple[int, int, int, int]]:
    crop_width, crop_height = min(width, DETAIL_EDGE), min(height, DETAIL_EDGE)
    xs, ys = _axis_positions(width), _axis_positions(height)
    boxes = []

    def select(values, size, extent, position):
        return ([0] if position in ("left", "top") else
                [size - extent] if position in ("right", "bottom") else
                [(size - extent) // 2] if position == "center" else values)

    for horizontal, vertical in regions or [("any", "any")]:
        selected_x = select(xs, width, crop_width, horizontal)
        selected_y = select(ys, height, crop_height, vertical)
        coordinates = [(x, y) for y in selected_y for x in selected_x]
        # For a very large image the bounded sample may not cover everything;
        # distribute samples over the region instead of consuming the budget
        # entirely along its first row. The prompt states this limitation.
        if len(coordinates) > DETAIL_CROP_LIMIT:
            indexes = [round(i * (len(coordinates) - 1) / (DETAIL_CROP_LIMIT - 1))
                       for i in range(DETAIL_CROP_LIMIT)]
            coordinates = [coordinates[index] for index in indexes]
        for x, y in coordinates:
            box = (x, y, x + crop_width, y + crop_height)
            if box not in boxes:
                boxes.append(box)
    return boxes


def detail_crops(images, prompt: str, cancel) -> tuple[list[tuple[bytes, str]], list[dict]]:
    """Return at most four PNG crops plus their safe, path-free provenance."""
    question, already_selected = _question_data(prompt)
    regions = _regions(question)
    ordinals = {"一": 0, "二": 1, "三": 2, "四": 3, "1": 0, "2": 1, "3": 2, "4": 3}
    requested = ({ordinals[value] for value in re.findall(
        r"(?:第\s*|图\s*|\bimage\s*)([一二三四1-4])(?:\s*张)?", question, re.I)}
        if not already_selected else set())
    originals, candidates = [], []
    try:
        for index, (data, _) in enumerate(images):
            if cancel.is_set():
                raise CodexCancelled("已停止本次图片任务。")
            if requested and index not in requested:
                continue
            with Image.open(BytesIO(data)) as source:
                if max(source.size) <= DETAIL_EDGE:
                    continue
                # Match the orientation of the overview the user sees.
                oriented = ImageOps.exif_transpose(source)
                if oriented.mode not in ("RGB", "RGBA", "L", "LA", "P", "I;16", "I;16B", "I;16L"):
                    oriented = oriented.convert("RGB")
                originals.append(oriented)
                candidates.append((index, oriented, _boxes(*oriented.size, regions)))
        crops, metadata = [], []
        # Round-robin preserves a detail view from every large input before
        # adding more tiles of the first one in a multi-image comparison.
        while len(crops) < DETAIL_CROP_LIMIT:
            added = False
            for index, source, boxes in candidates:
                if not boxes or len(crops) >= DETAIL_CROP_LIMIT:
                    continue
                if cancel.is_set():
                    raise CodexCancelled("已停止本次图片任务。")
                box = boxes.pop(0)
                with source.crop(box) as crop, BytesIO() as target:
                    crop.save(target, format="PNG", compress_level=1)
                    crops.append((target.getvalue(), ".png"))
                metadata.append({"attachmentIndex": len(images) + len(crops), "sourceImage": index + 1,
                                 "sourceSize": list(source.size), "box": list(box)})
                added = True
            if not added:
                break
        if cancel.is_set():
            raise CodexCancelled("已停止本次图片任务。")
        return crops, metadata
    except (OSError, ValueError, Image.DecompressionBombError, UnidentifiedImageError):
        raise CodexError("无法读取图片细节，请重新上传原图。") from None
    finally:
        for source in originals:
            source.close()


def crop_context(metadata: list[dict], original_count: int) -> str:
    if not metadata:
        return ""
    return (f"\n\n前 {original_count} 张附件是原图概览；其后的附件为原图局部像素的无损裁切，未放大、未生成新细节。"
            "请把局部裁切与对应全图共同判断，小字优先读取局部，不能将裁切误认成新增物体或独立场景。"
            "坐标以 EXIF 朝向纠正后的原图左上角为原点，box=[左,上,右,下]，右下边界不含；附件编号从 1 开始。"
            "裁切数量有上限，未覆盖区域可能仍只有缩小概览，不可宣称已核实那些微小细节。\n"
            + json.dumps({"detailCrops": metadata}, ensure_ascii=False))
