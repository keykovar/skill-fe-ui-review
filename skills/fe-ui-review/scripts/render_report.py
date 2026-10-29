#!/usr/bin/env python3
"""Render a portable HTML viewer and Markdown index from suite pixel evidence."""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path
from typing import Any

import compare_images


TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "report.html"
LABELS = {"reference": "参考图", "actual": "实际图", "overlay": "叠加图", "diff": "差异图"}
STRATEGIES = {"live": "LIVE · 真实网页", "fixture": "FIXTURE · 真实组件 + Mock 数据", "unrecorded": "未标注采集来源"}


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def image_uri(record: dict) -> str | None:
    """Embed only decoded raster files; never load report-controlled URLs or SVG."""
    path = record.get("path")
    if not path or compare_images.Image is None:
        return None
    try:
        source = Path(path)
        with compare_images.Image.open(source) as image:
            image.verify()
            mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image.format)
        if mime is None:
            return None
        return f"data:{mime};base64," + base64.b64encode(source.read_bytes()).decode("ascii")
    except (OSError, ValueError, compare_images.Image.DecompressionBombError):
        return None


def badge(verdict: str) -> str:
    style = verdict.lower() if verdict in ("PASS", "FAIL", "INCONCLUSIVE") else "inconclusive"
    return f'<span class="badge {style}">{escape(verdict)}</span>'


def download_link(uri: str, label: str, filename: str) -> str:
    mime = uri.split(";")[0].removeprefix("data:")
    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    return f'<a href="{uri}" download="{filename}.{extension}">{escape(label)}</a>'


def render_case(case: dict, index: int) -> str:
    verdict = case["verdict"]
    artifacts = case.get("artifacts", {})
    comparison_inputs = case.get("comparisonInputs", {})
    records = {"reference": comparison_inputs.get("reference", case.get("reference", {})), "actual": comparison_inputs.get("actual", case.get("actual", {})), "overlay": artifacts.get("overlay", {}), "diff": artifacts.get("diff", {})}
    images = {key: image_uri(record) for key, record in records.items()}
    valid = case.get("comparability", {}).get("valid") is True
    state = case.get("state", {}).get("name", "未声明状态")
    platform = case.get("platform", "unknown")
    collection = case.get("collection", {})
    strategy = collection.get("strategy", "unrecorded")
    strategy_label = STRATEGIES.get(strategy, "采集来源无效")
    preparation = case.get("preparation", {})
    normalized = preparation.get("status") == "APPLIED"
    color_note = "颜色处理：按提供图片的编码值比较；本次批量执行未新增 ICC 转换。已有预处理见证据记录。"
    if normalized:
        color_note = "颜色处理：按 ICC 转换为 sRGB 比较副本；下方视图与差异指标使用比较副本，输入原图单独保留并可下载。输入图片可能已按声明裁剪，完整采集范围见证据记录。"
        if any(record.get("operation") == "untagged-assumed-srgb" for record in preparation.get("inputs", {}).values()):
            color_note += " 未标记 ICC 的输入明确按 sRGB 处理。"
    elif preparation.get("status") in ("FAILED", "SKIPPED"):
        color_note = "颜色处理：已请求 sRGB，但转换未完成；当前案例不能进行有效像素判定。"
    metadata = f'{platform} · {case.get("deviceProfile") or "自定义尺寸"} · {state}'
    required = "必选案例" if case["required"] else "可选案例"
    issues = case.get("comparability", {}).get("issues", [])
    warnings = "".join(f'<li><code>{escape(item.get("code", "ISSUE"))}</code> — {escape(item.get("message", ""))}</li>' for item in issues)
    media = '<p class="empty">暂无可展示的图片。请先补齐采集结果。</p>'
    if valid and all(images.values()):
        size = records["reference"]["pixelSize"]
        controls = "".join(f'<button type="button" data-view="{key}" aria-pressed="false">{label}</button>' for key, label in LABELS.items())
        layers = "".join(f'<img data-image="{key}" src="{uri}" alt="{escape(LABELS[key])}" {"" if key in ("actual", "reference") else "hidden"}>' for key, uri in images.items())
        media = f'''
          <div class="view-controls" role="group" aria-label="图片视图">
            <button type="button" data-view="split" aria-pressed="true">拖动对比</button>{controls}
            <button type="button" data-zoom aria-pressed="false">放大 2×</button>
          </div>
          <div class="zoom-viewport" tabindex="0" aria-label="图片区域，放大后可滚动查看">
            <div class="image-stage" data-mode="split" style="aspect-ratio:{int(size['width'])}/{int(size['height'])};--image-ratio:{size['width'] / size['height']:.10f}">
              {layers}<span class="divider" aria-hidden="true"></span>
            </div>
          </div>
          <label class="slider-label">参考图显示比例
            <input type="range" min="0" max="100" value="50" data-slider aria-label="参考图显示比例">
            <output>50%</output>
          </label>
          <p class="muted">左侧参考图，右侧实际图；展示缩放不参与判定。原始尺寸 {size['width']} × {size['height']} px。</p>
        '''
    elif not valid and any(images.values()):
        figures = "".join(f'<figure><img src="{uri}" alt="{escape(LABELS[key])}"><figcaption>{LABELS[key]} · 比较无效，仅供排查</figcaption></figure>' for key, uri in images.items() if uri and key in ("reference", "actual"))
        media = f'<p class="invalid-label">比较无效：以下图片不能作为通过验收的证据。</p><div class="invalid-images">{figures}</div>'
    elif valid:
        media = '<p class="empty">图片预览不可用。请检查原始文件和 result.json；显示失败不会改变已记录的像素指标。</p>'

    metrics = case.get("metrics", {})
    effective = metrics.get("effective", {})
    ratio = effective.get("diffRatio")
    ratio_text = f"{ratio:.4%}" if isinstance(ratio, (float, int)) else "—"
    raw_ratio = metrics.get("raw", {}).get("diffRatio")
    raw_text = f"{raw_ratio:.4%}" if isinstance(raw_ratio, (float, int)) else "—"
    download_links = []
    for key, uri in images.items():
        if uri:
            label = f'下载{"sRGB比较" if normalized and key in ("reference", "actual") else ""}{LABELS[key]}'
            download_links.append(download_link(uri, label, f"case-{index}-{key}"))
    if normalized:
        for key in ("reference", "actual"):
            uri = image_uri(case.get(key, {}))
            if uri:
                download_links.append(download_link(uri, f"下载输入原图（{LABELS[key]}）", f"case-{index}-source-{key}"))
    downloads = "".join(download_links)
    audit = {key: case.get(key) for key in ("collection", "reference", "actual", "comparisonInputs", "preparation", "normalizedEnvironment", "state", "capture", "resolvedThresholds", "declaredMasks", "metrics")}
    search = f'{case["id"]} {metadata} {strategy_label} {collection.get("subjectId", "")}'
    scope_note = "仅验证该代码版本与固定数据的视觉表现；不证明测试站部署、真实接口或账号流程通过。" if strategy == "fixture" else "采集真实站点当时的页面状态；代码版本未知时不与本地版本视为一致。" if strategy == "live" else "截图来源未标注，不推断为线上或 Mock。"
    findings = "".join(f'<li><strong>{escape(item.get("id", ""))} · {escape(item.get("severity", ""))}</strong> — {escape(item.get("observation", ""))}<p>{escape(item.get("repair", ""))}</p></li>' for item in case.get("findings", []))
    limitations = "".join(f'<li>{escape(item)}</li>' for item in case.get("limitations", []))
    analysis_label = "待 Agent 审查" if case.get("analysisStatus") == "PENDING_AGENT_REVIEW" else "已描述差异，存在证据缺口"
    return f'''
      <article class="case" data-verdict="{escape(verdict)}" data-platform="{escape(platform)}" data-strategy="{escape(strategy)}" data-search="{escape(search.lower())}">
        <header class="case-header"><div><h2>{escape(case['id'])}</h2><p class="muted">{escape(metadata)} · {required}</p></div>{badge(verdict)}</header>
        <p class="scope"><strong>{escape(strategy_label)}</strong> — {escape(scope_note)}</p>
        <p class="muted color-processing">{escape(color_note)}</p>
        {'<p class="invalid-label">仅测量差异：截图可比较，尚未设置验收阈值，不作 PASS/FAIL 判定。</p>' if case.get('measurementOnly') else ''}
        <dl class="metrics"><div><dt>遮罩后差异</dt><dd>{ratio_text}</dd></div><div><dt>遮罩前差异</dt><dd>{raw_text}</dd></div><div><dt>遮罩覆盖</dt><dd>{metrics.get('maskedRatio', 0):.2%}</dd></div><div><dt>分析状态</dt><dd>{analysis_label}</dd></div></dl>
        {f'<ul class="issues">{warnings}</ul>' if warnings else ''}
        {media}
        {f'<h3>差异与修复建议</h3><ul>{findings}</ul>' if findings else ''}
        {f'<details><summary>本次比较的范围与限制</summary><ul>{limitations}</ul></details>' if limitations else ''}
        <nav class="downloads" aria-label="证据图片下载">{downloads}</nav>
        <details><summary>环境、阈值与证据记录</summary><pre>{escape(json.dumps(audit, ensure_ascii=False, indent=2))}</pre></details>
        <p class="next-action"><strong>下一步：</strong>{escape(case.get('nextAction', '补充审查结论。'))}</p>
      </article>
    '''


def write_reports(report: dict, output_dir: Path) -> None:
    cases = report["cases"]
    summary = report["summary"]
    options = "".join(f'<option value="{escape(platform)}">{escape(platform)}</option>' for platform in sorted({case["platform"] for case in cases}))
    parts = {
        "TITLE": escape(report["suiteId"]), "VERDICT": badge(report["suiteVerdict"]),
        "TIME": escape(report["finishedAt"]),
        "TOTAL": str(summary["total"]), "REQUIRED": str(summary["required"]),
        "PASS": str(summary["pass"]), "FAIL": str(summary["fail"]), "INCONCLUSIVE": str(summary["inconclusive"]),
        "PLATFORMS": options,
        "STRATEGIES": "".join(f'<option value="{key}">{escape(label)}</option>' for key, label in STRATEGIES.items()),
        "STRATEGYSUMMARY": "".join(f'<p>{escape(STRATEGIES.get(key, key))}: {badge(value["verdict"])} · PASS {value["pass"]} / FAIL {value["fail"]} / INCONCLUSIVE {value["inconclusive"]}</p>' for key, value in report.get("strategySummary", {}).items()),
        "CASES": "".join(render_case(case, index) for index, case in enumerate(cases)),
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    content = re.sub(r"@@([A-Z]+)@@", lambda match: parts[match[1]], template)
    (output_dir / "report.html").write_text(content, encoding="utf-8")
    lines = [f"# {report['suiteId']}", "", f"Pixel comparison: **{report['suiteVerdict']}**", "", "Scope: prepared local captures and explicit pixel thresholds only. Agent review of page state, geometry, critical regions and accessibility is still required. Device presets do not prove physical-device coverage.", "", f"Total: {summary['total']}; required: {summary['required']}; PASS: {summary['pass']}; FAIL: {summary['fail']}; INCONCLUSIVE: {summary['inconclusive']}.", "", f"[Interactive report]({output_dir / 'report.html'}) · [JSON]({output_dir / 'report.json'})", ""]
    for case in cases:
        strategy = case.get("collection", {}).get("strategy", "unrecorded")
        lines.extend([f"## {case['id']} — {case['verdict']}", "", f"Platform: {case['platform']}; required: {case['required']}; collection: {STRATEGIES.get(strategy, strategy)}.", ""])
        preparation = case.get("preparation", {})
        lines.extend([f"Color preparation: {preparation.get('colorSpace', 'encoded')}; status: {preparation.get('status', 'NOT_REQUESTED')}. Original source hashes and comparison inputs are recorded separately in report.json.", ""])
        for item in case.get("comparability", {}).get("issues", []):
            lines.extend([f"- {item['code']}: {item['message']}", ""])
        board = case.get("artifacts", {}).get("comparisonBoard", {}).get("path")
        if board and case["comparability"]["valid"]:
            lines.extend([f"![UI comparison board]({board})", ""])
        for finding in case.get("findings", []):
            lines.extend([f"- {finding.get('id', '')}: {finding.get('observation', '')}", f"  修复建议：{finding.get('repair', '')}", ""])
        if case.get("limitations"):
            lines.extend(["比较范围与限制：", ""])
            for limitation in case["limitations"]:
                lines.extend([f"- {limitation}", ""])
        lines.extend([case["nextAction"], ""])
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
